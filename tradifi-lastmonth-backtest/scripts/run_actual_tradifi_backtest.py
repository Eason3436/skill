from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ccxt


TAIPEI = ZoneInfo("Asia/Taipei")
HIGH_VOL_BLACKLIST = {"ASTS", "AXTI", "CRDO", "ORCL", "RKLB", "SOXL", "SPCX"}


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_ts: datetime
    exit_ts: datetime
    side: str
    notional: float
    entry_basis: float
    exit_basis: float
    gross: float
    fees: float
    funding: float
    net: float
    exit_reason: str
    taker_fees: float = 0.0
    slippage: float = 0.0


@dataclass(frozen=True)
class SymbolPoint:
    ts: datetime
    symbol: str
    basis: float
    reversion_improvement: float = 0.0
    b_price: float = 0.0
    o_price: float = 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Actual Binance/OKX TRADIFI perp backtest from historical candles.")
    parser.add_argument("--capital", type=float, default=100.0)
    parser.add_argument("--leverage", type=int, default=5)
    parser.add_argument("--start", default="2026-06-08", help="Taipei date YYYY-MM-DD, inclusive.")
    parser.add_argument("--end", default="2026-06-14", help="Taipei date YYYY-MM-DD, inclusive.")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--entry", type=float, default=0.0030)
    parser.add_argument("--exit", type=float, default=0.0010)
    parser.add_argument("--maker-fee", type=float, default=0.0002)
    parser.add_argument("--funding-buffer", type=float, default=0.0)
    # ── Execution-cost / slippage simulation (opt-in via --simulate-costs) ──────
    parser.add_argument("--simulate-costs", action="store_true",
                        help="Enable realistic fill/slippage simulation (taker fees, per-leg slippage, "
                             "partial fills, single-leg retreats, forced-close slippage).")
    parser.add_argument("--taker-fee", type=float, default=0.0005,
                        help="Taker fee per leg, charged when a close crosses the spread (time stops, single-leg closes).")
    parser.add_argument("--slippage-per-leg", type=float, default=0.0005,
                        help="Execution slippage vs mid charged on every filled leg (entry + exit).")
    parser.add_argument("--fill-rate", type=float, default=0.90,
                        help="Probability both post-only open legs fill and a position is opened.")
    parser.add_argument("--single-leg-rate", type=float, default=0.05,
                        help="Probability an open attempt fills only one leg and must be retreated at a loss.")
    parser.add_argument("--close-fill-rate", type=float, default=0.80,
                        help="Probability both close legs fill as maker; otherwise one leg pays taker + retreat slippage.")
    parser.add_argument("--retreat-slippage", type=float, default=0.0020,
                        help="Slippage paid when unwinding a single leg (open retreat / single-leg close).")
    parser.add_argument("--forced-close-slippage", type=float, default=0.0030,
                        help="Per-leg slippage paid when a position is force-closed on a time stop.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for the fill/slippage simulation.")
    # ── Per-leg liquidation modelling (leverage actually matters here) ──────────
    parser.add_argument("--model-liquidation", action="store_true",
                        help="Track each leg's price drawdown while a position is open and force-close "
                             "(with a liquidation penalty) when one leg breaches maintenance margin.")
    parser.add_argument("--maintenance-margin", type=float, default=0.01,
                        help="Maintenance-margin rate per leg; liquidation triggers at adverse move >= 1/leverage - mmr.")
    parser.add_argument("--liq-penalty", type=float, default=0.0075,
                        help="Liquidation penalty (fee + bankruptcy-price gap) charged on notional when a leg is liquidated.")
    parser.add_argument("--auto-flatten-buffer", type=float, default=0.0,
                        help="If >0, pre-emptively close BOTH legs (taker, no liquidation penalty) when the worst leg "
                             "loss reaches (1/leverage - mmr - buffer). Models a protective auto-flatten circuit breaker.")
    parser.add_argument("--max-hold-minutes", type=int, default=90)
    parser.add_argument("--force-close-end", action="store_true", help="Close any remaining open spread at the final candle.")
    parser.add_argument("--min-edge", type=float, default=0.0005)
    parser.add_argument("--reversion-lookback-bars", type=int, default=0)
    parser.add_argument("--min-reversion-improvement", type=float, default=0.0)
    parser.add_argument("--exclude-symbols", default="", help="Comma-separated base symbols to skip, e.g. OPENAI,CRWV.")
    parser.add_argument("--symbols", default="", help="Comma-separated base symbols to include. Empty means all common symbols.")
    parser.add_argument("--max-symbols", type=int, default=0, help="Debug limiter; 0 means all common symbols.")
    parser.add_argument("--cache", type=Path, default=ROOT / "reports" / "tradifi_cache")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "tradifi_actual_100u_5x_daily.json")
    parser.add_argument("--csv-out", type=Path, default=ROOT / "reports" / "tradifi_actual_100u_5x_daily.csv")
    args = parser.parse_args()

    start_tpe = datetime.fromisoformat(args.start).replace(tzinfo=TAIPEI)
    end_tpe = (datetime.fromisoformat(args.end).replace(tzinfo=TAIPEI) + timedelta(days=1))
    start_utc = start_tpe.astimezone(timezone.utc)
    end_utc = end_tpe.astimezone(timezone.utc)

    binance = ccxt.binanceusdm({"enableRateLimit": True})
    okx = ccxt.okx({"enableRateLimit": True})
    try:
        common = discover_common_tradifi(binance, okx)
    except Exception as exc:
        # Offline / restricted network: fall back to the symbol universe already
        # present in the on-disk OHLCV cache for this timeframe + date range.
        common = discover_common_from_cache(args.cache, args.timeframe, start_utc, end_utc)
        if not common:
            raise
        print(
            f"[offline] market discovery unavailable ({type(exc).__name__}); "
            f"using {len(common)} symbols from cache for {args.timeframe} {args.start}..{args.end}",
            file=sys.stderr,
        )
    include_symbols = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}
    if include_symbols:
        common = [symbol for symbol in common if symbol in include_symbols]
    if args.max_symbols:
        common = common[: args.max_symbols]
    excluded_symbols = {item.strip().upper() for item in args.exclude_symbols.split(",") if item.strip()}

    per_leg_notional = args.capital * args.leverage / 2.0
    series: dict[str, list[SymbolPoint]] = {}
    skipped: dict[str, str] = {}
    for idx, base in enumerate(common, start=1):
        if base in excluded_symbols:
            skipped[base] = "manual_exclude"
            continue
        if base in HIGH_VOL_BLACKLIST:
            skipped[base] = "high_volatility_blacklist"
            continue
        try:
            b_symbol = f"{base}/USDT:USDT"
            o_symbol = f"{base}/USDT:USDT"
            b_rows = cached_ohlcv(binance, b_symbol, args.timeframe, start_utc, end_utc, args.cache / "binance")
            o_rows = cached_ohlcv(okx, o_symbol, args.timeframe, start_utc, end_utc, args.cache / "okx")
        except Exception as exc:
            skipped[base] = f"fetch_failed:{type(exc).__name__}:{exc}"
            continue
        rows = align_closes(b_rows, o_rows, start_utc, end_utc)
        if len(rows) < 30:
            skipped[base] = f"insufficient_aligned_candles:{len(rows)}"
            continue
        series[base] = build_basis_series(base, rows, args.reversion_lookback_bars)
        time.sleep(0.05)

    cost_rng = random.Random(args.seed) if args.simulate_costs else None
    trades = run_portfolio_backtest(
        series,
        notional=per_leg_notional,
        entry_threshold=args.entry,
        exit_threshold=args.exit,
        maker_fee=args.maker_fee,
        funding_buffer=args.funding_buffer,
        max_hold_minutes=args.max_hold_minutes,
        min_edge=args.min_edge,
        force_close_end=args.force_close_end,
        min_reversion_improvement=args.min_reversion_improvement,
        taker_fee=args.taker_fee,
        slippage_per_leg=args.slippage_per_leg,
        fill_rate=args.fill_rate,
        single_leg_rate=args.single_leg_rate,
        close_fill_rate=args.close_fill_rate,
        retreat_slippage=args.retreat_slippage,
        forced_close_slippage=args.forced_close_slippage,
        rng=cost_rng,
        leverage=args.leverage if args.model_liquidation else 0,
        maintenance_margin=args.maintenance_margin,
        liq_penalty=args.liq_penalty,
        auto_flatten_buffer=args.auto_flatten_buffer,
    )
    daily = daily_summary(trades, args.capital, start_tpe.date(), (end_tpe - timedelta(days=1)).date())
    result = {
        "assumptions": {
            "capital_total_usdt": args.capital,
            "leverage": args.leverage,
            "capital_split": "50 USDT equivalent margin per exchange; per-leg notional = capital * leverage / 2",
            "per_leg_notional_usdt": per_leg_notional,
            "portfolio_constraint": "single spread open at a time; no capital reuse across symbols; fixed size based on starting capital",
            "force_close_end": args.force_close_end,
            "timeframe": args.timeframe,
            "date_range_taipei": {"start": args.start, "end": args.end},
            "entry_threshold": args.entry,
            "exit_threshold": args.exit,
            "reversion_lookback_bars": args.reversion_lookback_bars,
            "min_reversion_improvement": args.min_reversion_improvement,
            "excluded_symbols": sorted(excluded_symbols),
            "maker_fee": args.maker_fee,
            "round_trip_maker_fee": args.maker_fee * 4,
            "simulate_costs": args.simulate_costs,
            "model_liquidation": args.model_liquidation,
            "liquidation_model": (
                {
                    "leverage": args.leverage,
                    "maintenance_margin": args.maintenance_margin,
                    "liq_threshold_adverse_move": round(1.0 / args.leverage - args.maintenance_margin, 6),
                    "liq_penalty": args.liq_penalty,
                    "auto_flatten_buffer": args.auto_flatten_buffer,
                }
                if args.model_liquidation
                else None
            ),
            "cost_model": (
                {
                    "taker_fee": args.taker_fee,
                    "slippage_per_leg": args.slippage_per_leg,
                    "fill_rate": args.fill_rate,
                    "single_leg_rate": args.single_leg_rate,
                    "close_fill_rate": args.close_fill_rate,
                    "retreat_slippage": args.retreat_slippage,
                    "forced_close_slippage": args.forced_close_slippage,
                    "seed": args.seed,
                }
                if args.simulate_costs
                else None
            ),
            "historical_data": f"Binance/OKX {args.timeframe} OHLCV close prices; no historical L2 queue simulation",
        },
        "symbol_count": len(common),
        "skipped": skipped,
        "daily": daily,
        "totals": totals(trades, daily),
        "symbol_stats": symbol_stats(trades),
        "trades": [trade_to_dict(t) for t in trades],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_daily_csv(args.csv_out, daily)
    print(json.dumps({"daily": daily, "totals": result["totals"], "skipped_count": len(skipped)}, ensure_ascii=False, indent=2))
    return 0


def discover_common_tradifi(binance, okx) -> list[str]:
    binance_markets = binance.load_markets()
    okx_markets = okx.load_markets()
    bin_bases = {
        m["base"]
        for m in binance_markets.values()
        if m.get("swap")
        and m.get("quote") == "USDT"
        and "TRADIFI" in str((m.get("info") or {}).get("contractType") or "")
        and (m.get("info") or {}).get("status") == "TRADING"
    }
    okx_bases = {
        m["base"]
        for m in okx_markets.values()
        if m.get("swap")
        and m.get("quote") == "USDT"
        and str((m.get("info") or {}).get("instCategory") or "") == "3"
        and (m.get("info") or {}).get("state") == "live"
    }
    return sorted(bin_bases & okx_bases)


def discover_common_from_cache(cache_root: Path, timeframe: str, start: datetime, end: datetime) -> list[str]:
    """Derive the common Binance/OKX symbol universe from on-disk OHLCV cache.

    Used when live market discovery is unavailable (offline / restricted network).
    Matches the exact ``{base}_USDT_USDT_{timeframe}_{start}_{end}.json`` files the
    backtest would read, so the offline universe is consistent with the cache.
    """
    suffix = f"_USDT_USDT_{timeframe}_{int(start.timestamp())}_{int(end.timestamp())}.json"

    def bases(sub: str) -> set[str]:
        directory = cache_root / sub
        if not directory.is_dir():
            return set()
        return {p.name[: -len(suffix)] for p in directory.glob(f"*{suffix}")}

    return sorted(bases("binance") & bases("okx"))


def cached_ohlcv(exchange, symbol: str, timeframe: str, start: datetime, end: datetime, cache_dir: Path) -> list[list[float]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/", "_").replace(":", "_")
    path = cache_dir / f"{safe}_{timeframe}_{int(start.timestamp())}_{int(end.timestamp())}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    since = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    all_rows: list[list[float]] = []
    while since < end_ms:
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=500)
        if not rows:
            break
        for row in rows:
            if since <= int(row[0]) < end_ms:
                all_rows.append(row)
        last = int(rows[-1][0])
        next_since = last + timeframe_ms(timeframe)
        if next_since <= since:
            break
        since = next_since
        time.sleep(exchange.rateLimit / 1000.0 if getattr(exchange, "rateLimit", None) else 0.05)

    dedup = {int(row[0]): row for row in all_rows}
    result = [dedup[ts] for ts in sorted(dedup)]
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def align_closes(b_rows: list[list[float]], o_rows: list[list[float]], start: datetime, end: datetime) -> list[tuple[datetime, float, float]]:
    b = {int(row[0]): float(row[4]) for row in b_rows if float(row[4]) > 0}
    o = {int(row[0]): float(row[4]) for row in o_rows if float(row[4]) > 0}
    out = []
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    for ts in sorted(set(b) & set(o)):
        if start_ms <= ts < end_ms:
            out.append((datetime.fromtimestamp(ts / 1000, tz=timezone.utc), b[ts], o[ts]))
    return out


def build_basis_series(
    symbol: str,
    rows: list[tuple[datetime, float, float]],
    reversion_lookback_bars: int = 0,
) -> list[SymbolPoint]:
    basis_values = [(b / o - 1.0) for _, b, o in rows if o > 0]
    if not basis_values:
        return []
    basis_mean = mean(basis_values)
    points: list[SymbolPoint] = []
    for idx, (ts, b, o) in enumerate(rows):
        if o <= 0:
            continue
        basis = (b / o - 1.0) - basis_mean
        improvement = 0.0
        if reversion_lookback_bars > 0 and idx > 0:
            start = max(0, idx - reversion_lookback_bars)
            previous_abs = [abs((rows[j][1] / rows[j][2] - 1.0) - basis_mean) for j in range(start, idx) if rows[j][2] > 0]
            if previous_abs:
                improvement = max(previous_abs) - abs(basis)
        points.append(SymbolPoint(ts, symbol, basis, improvement, b_price=b, o_price=o))
    return points


def run_portfolio_backtest(
    series: dict[str, list[SymbolPoint]],
    *,
    notional: float,
    entry_threshold: float,
    exit_threshold: float,
    maker_fee: float,
    funding_buffer: float,
    max_hold_minutes: int,
    min_edge: float,
    force_close_end: bool = False,
    min_reversion_improvement: float = 0.0,
    taker_fee: float = 0.0005,
    slippage_per_leg: float = 0.0005,
    fill_rate: float = 0.90,
    single_leg_rate: float = 0.05,
    close_fill_rate: float = 0.80,
    retreat_slippage: float = 0.0020,
    forced_close_slippage: float = 0.0030,
    rng: random.Random | None = None,
    leverage: int = 0,
    maintenance_margin: float = 0.01,
    liq_penalty: float = 0.0075,
    auto_flatten_buffer: float = 0.0,
) -> list[Trade]:
    by_ts: dict[datetime, list[SymbolPoint]] = {}
    for points in series.values():
        for point in points:
            by_ts.setdefault(point.ts, []).append(point)

    # Adverse per-leg move that wipes the maintenance margin (liquidation), and the
    # earlier protective auto-flatten threshold if a circuit breaker is configured.
    liq_threshold = (1.0 / leverage - maintenance_margin) if leverage > 0 else None
    flatten_threshold = (
        liq_threshold - auto_flatten_buffer
        if liq_threshold is not None and auto_flatten_buffer > 0
        else None
    )

    def _side(point: SymbolPoint) -> str:
        return "short_binance_long_okx" if point.basis > 0 else "long_binance_short_okx"

    def _worst_leg_loss(entry: SymbolPoint, current: SymbolPoint) -> float:
        """Worst (most negative) single-leg PnL fraction since entry; >0 means a loss."""
        if entry.b_price <= 0 or entry.o_price <= 0:
            return 0.0
        if entry.basis > 0:  # short Binance, long OKX
            b_leg = (entry.b_price - current.b_price) / entry.b_price
            o_leg = (current.o_price - entry.o_price) / entry.o_price
        else:  # long Binance, short OKX
            b_leg = (current.b_price - entry.b_price) / entry.b_price
            o_leg = (entry.o_price - current.o_price) / entry.o_price
        return -min(b_leg, o_leg)

    def _liquidate(entry: SymbolPoint, current: SymbolPoint) -> Trade:
        # Forced unwind at the adverse point: spread PnL to here + both legs taker-closed,
        # plus a liquidation penalty (fee + bankruptcy-price gap) on the wiped leg.
        gross = (abs(entry.basis) - abs(current.basis)) * notional
        fees = notional * maker_fee * 2
        taker = notional * taker_fee * 2
        slip = notional * slippage_per_leg * 2 + notional * forced_close_slippage * 2 + notional * liq_penalty
        net = gross - fees - taker - slip
        return Trade(
            symbol=entry.symbol, entry_ts=entry.ts, exit_ts=current.ts, side=_side(entry),
            notional=notional, entry_basis=entry.basis, exit_basis=current.basis,
            gross=gross, fees=fees, funding=0.0, net=net, exit_reason="liquidation",
            taker_fees=taker, slippage=slip,
        )

    def _close(entry: SymbolPoint, current: SymbolPoint, *, converged: bool, reason: str) -> Trade:
        gross = (abs(entry.basis) - abs(current.basis)) * notional
        if rng is None:
            # ── Legacy, frictionless accounting (no fill/slippage simulation). ──
            fees = notional * maker_fee * 4
            funding = notional * funding_buffer if reason != "converged" else 0.0
            taker = 0.0
            slip = 0.0
            exit_reason = reason
        elif converged:
            # Entry was a clean two-leg maker fill: 2 maker legs + 2 legs of slippage.
            if rng.random() < close_fill_rate:
                fees = notional * maker_fee * 4
                taker = 0.0
                slip = notional * slippage_per_leg * 4
                exit_reason = "converged"
            else:
                # One close leg slips to taker and pays retreat slippage.
                fees = notional * maker_fee * 3
                taker = notional * taker_fee
                slip = notional * slippage_per_leg * 3 + notional * retreat_slippage
                exit_reason = "converged_single_leg_close"
            funding = 0.0
        else:
            # Forced close (time stop / end of period): both legs cross the spread.
            fees = notional * maker_fee * 2
            taker = notional * taker_fee * 2
            slip = notional * slippage_per_leg * 2 + notional * forced_close_slippage * 2
            funding = notional * funding_buffer
            exit_reason = reason
        net = gross - fees - taker - funding - slip
        return Trade(
            symbol=entry.symbol,
            entry_ts=entry.ts,
            exit_ts=current.ts,
            side=_side(entry),
            notional=notional,
            entry_basis=entry.basis,
            exit_basis=current.basis,
            gross=gross,
            fees=fees,
            funding=funding,
            net=net,
            exit_reason=exit_reason,
            taker_fees=taker,
            slippage=slip,
        )

    open_pos: SymbolPoint | None = None
    last_by_symbol: dict[str, SymbolPoint] = {}
    trades: list[Trade] = []
    for ts in sorted(by_ts):
        points = by_ts[ts]
        point_by_symbol = {point.symbol: point for point in points}
        last_by_symbol.update(point_by_symbol)
        if open_pos is not None:
            current = point_by_symbol.get(open_pos.symbol)
            if current is None:
                continue
            # Per-leg liquidation / protective auto-flatten check (leverage-dependent).
            if liq_threshold is not None:
                leg_loss = _worst_leg_loss(open_pos, current)
                if leg_loss >= liq_threshold:
                    trades.append(_liquidate(open_pos, current))
                    open_pos = None
                    continue
                if flatten_threshold is not None and leg_loss >= flatten_threshold:
                    # Circuit breaker: close both legs at market before liquidation (no penalty).
                    trades.append(_close(open_pos, current, converged=False, reason="auto_flatten"))
                    open_pos = None
                    continue
            hold_minutes = (current.ts - open_pos.ts).total_seconds() / 60.0
            converged = abs(current.basis) <= exit_threshold
            timed_out = hold_minutes >= max_hold_minutes
            if converged or timed_out:
                trades.append(
                    _close(open_pos, current, converged=converged, reason="converged" if converged else "time_stop")
                )
                open_pos = None
            continue

        candidates = []
        for point in points:
            abs_basis = abs(point.basis)
            expected_edge = abs_basis - exit_threshold - maker_fee * 4 - funding_buffer
            has_reversion = point.reversion_improvement >= min_reversion_improvement
            if abs_basis >= entry_threshold and expected_edge >= min_edge and has_reversion:
                candidates.append((expected_edge, point))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        chosen = candidates[0][1]
        if rng is None:
            open_pos = chosen
            continue
        # Simulate post-only entry: both legs fill / single-leg retreat / no fill.
        roll = rng.random()
        if roll < single_leg_rate:
            fees = notional * maker_fee
            taker = notional * taker_fee
            slip = notional * retreat_slippage
            trades.append(
                Trade(
                    symbol=chosen.symbol,
                    entry_ts=chosen.ts,
                    exit_ts=chosen.ts,
                    side=_side(chosen),
                    notional=notional,
                    entry_basis=chosen.basis,
                    exit_basis=chosen.basis,
                    gross=0.0,
                    fees=fees,
                    funding=0.0,
                    net=-(fees + taker + slip),
                    exit_reason="single_leg_retreat",
                    taker_fees=taker,
                    slippage=slip,
                )
            )
        elif roll < single_leg_rate + fill_rate:
            open_pos = chosen
        # else: both legs missed; stay flat and keep scanning.
    if force_close_end and open_pos is not None and open_pos.symbol in last_by_symbol:
        trades.append(_close(open_pos, last_by_symbol[open_pos.symbol], converged=False, reason="end_of_period"))
    return trades


def run_symbol_backtest(
    symbol: str,
    rows: list[tuple[datetime, float, float]],
    *,
    notional: float,
    entry_threshold: float,
    exit_threshold: float,
    maker_fee: float,
    funding_buffer: float,
    max_hold_minutes: int,
    min_edge: float,
) -> list[Trade]:
    basis_values = [(b / o - 1.0) for _, b, o in rows if o > 0]
    if not basis_values:
        return []
    basis_mean = mean(basis_values)
    trades: list[Trade] = []
    open_pos: dict | None = None
    for ts, b_close, o_close in rows:
        basis = (b_close / o_close - 1.0) - basis_mean
        if open_pos is None:
            abs_basis = abs(basis)
            expected_edge = abs_basis - exit_threshold - maker_fee * 4 - funding_buffer
            if abs_basis >= entry_threshold and expected_edge >= min_edge:
                open_pos = {
                    "ts": ts,
                    "basis": basis,
                    "side": "short_binance_long_okx" if basis > 0 else "long_binance_short_okx",
                }
            continue

        hold_minutes = (ts - open_pos["ts"]).total_seconds() / 60.0
        converged = abs(basis) <= exit_threshold
        timed_out = hold_minutes >= max_hold_minutes
        if not converged and not timed_out:
            continue

        gross = (abs(open_pos["basis"]) - abs(basis)) * notional
        fees = notional * maker_fee * 4
        funding = notional * funding_buffer if timed_out else 0.0
        net = gross - fees - funding
        trades.append(
            Trade(
                symbol=symbol,
                entry_ts=open_pos["ts"],
                exit_ts=ts,
                side=open_pos["side"],
                notional=notional,
                entry_basis=open_pos["basis"],
                exit_basis=basis,
                gross=gross,
                fees=fees,
                funding=funding,
                net=net,
                exit_reason="converged" if converged else "time_stop",
            )
        )
        open_pos = None
    return trades


def daily_summary(trades: list[Trade], capital: float, start_date, end_date) -> list[dict[str, float | int | str]]:
    days = []
    equity = capital
    day = start_date
    by_day: dict[str, list[Trade]] = {}
    for trade in trades:
        key = trade.exit_ts.astimezone(TAIPEI).date().isoformat()
        by_day.setdefault(key, []).append(trade)
    while day <= end_date:
        key = day.isoformat()
        items = by_day.get(key, [])
        net = sum(t.net for t in items)
        equity += net
        wins = sum(1 for t in items if t.net > 0)
        days.append(
            {
                "date_taipei": key,
                "trades": len(items),
                "wins": wins,
                "losses": len(items) - wins,
                "net_pnl_usdt": round(net, 6),
                "return_on_starting_capital_pct": round(net / capital * 100.0, 4) if capital else 0.0,
                "ending_equity_usdt": round(equity, 6),
            }
        )
        day += timedelta(days=1)
    return days


def totals(trades: list[Trade], daily: list[dict]) -> dict[str, float | int]:
    total_net = sum(t.net for t in trades)
    return {
        "trades": len(trades),
        "wins": sum(1 for t in trades if t.net > 0),
        "losses": sum(1 for t in trades if t.net <= 0),
        "gross_pnl_usdt": round(sum(t.gross for t in trades), 6),
        "maker_fees_usdt": round(sum(t.fees for t in trades), 6),
        "taker_fees_usdt": round(sum(t.taker_fees for t in trades), 6),
        "slippage_usdt": round(sum(t.slippage for t in trades), 6),
        "funding_usdt": round(sum(t.funding for t in trades), 6),
        "net_pnl_usdt": round(total_net, 6),
        "ending_equity_usdt": daily[-1]["ending_equity_usdt"] if daily else 0.0,
        "best_trade_usdt": round(max((t.net for t in trades), default=0.0), 6),
        "worst_trade_usdt": round(min((t.net for t in trades), default=0.0), 6),
        "single_leg_retreats": sum(1 for t in trades if t.exit_reason == "single_leg_retreat"),
        "time_stops": sum(1 for t in trades if t.exit_reason == "time_stop"),
        "liquidations": sum(1 for t in trades if t.exit_reason == "liquidation"),
        "auto_flattens": sum(1 for t in trades if t.exit_reason == "auto_flatten"),
    }


def symbol_stats(trades: list[Trade]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[Trade]] = {}
    for trade in trades:
        grouped.setdefault(trade.symbol, []).append(trade)
    out: dict[str, dict[str, float | int]] = {}
    for symbol, items in sorted(grouped.items()):
        wins = sum(1 for item in items if item.net > 0)
        time_stops = sum(1 for item in items if item.exit_reason == "time_stop")
        net = sum(item.net for item in items)
        out[symbol] = {
            "trades": len(items),
            "wins": wins,
            "losses": len(items) - wins,
            "win_rate": round(wins / len(items), 4) if items else 0.0,
            "time_stops": time_stops,
            "time_stop_rate": round(time_stops / len(items), 4) if items else 0.0,
            "net_pnl_usdt": round(net, 6),
        }
    return out


def timeframe_ms(timeframe: str) -> int:
    if timeframe.endswith("m"):
        return int(timeframe[:-1]) * 60_000
    if timeframe.endswith("H") or timeframe.endswith("h"):
        return int(timeframe[:-1]) * 3_600_000
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def trade_to_dict(trade: Trade) -> dict:
    return {
        "symbol": trade.symbol,
        "entry_ts": trade.entry_ts.isoformat(),
        "exit_ts": trade.exit_ts.isoformat(),
        "side": trade.side,
        "notional": trade.notional,
        "entry_basis": trade.entry_basis,
        "exit_basis": trade.exit_basis,
        "reversion_improvement": 0.0,
        "gross": trade.gross,
        "fees": trade.fees,
        "taker_fees": trade.taker_fees,
        "slippage": trade.slippage,
        "funding": trade.funding,
        "net": trade.net,
        "exit_reason": trade.exit_reason,
    }


def write_daily_csv(path: Path, daily: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(daily[0].keys()) if daily else [])
        if daily:
            writer.writeheader()
            writer.writerows(daily)


if __name__ == "__main__":
    raise SystemExit(main())
