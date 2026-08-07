"""Performance statistics for a backtest result."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _daily_returns(equity: pd.Series) -> pd.Series:
    daily = equity.resample("1D").last().dropna()
    return daily.pct_change().dropna()


def max_drawdown(equity: pd.Series) -> tuple[float, pd.Timestamp | None]:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    if dd.empty:
        return 0.0, None
    return float(dd.min() * 100.0), dd.idxmin()


def summarize(res: dict) -> dict:
    eq = res["equity"]
    tr = res["trades"]
    p = res["params"]
    init = p["init_equity"]

    out: dict = {
        "trades": int(len(tr)),
        "final_equity": float(res["final_equity"]),
        "total_return_pct": float((res["final_equity"] / init - 1.0) * 100.0),
    }
    if eq.empty:
        return out

    days = max((eq.index[-1] - eq.index[0]).days, 1)
    out["days"] = days
    out["cagr_pct"] = float(((res["final_equity"] / init) ** (365.0 / days) - 1.0) * 100.0)

    rets = _daily_returns(eq)
    if len(rets) > 1 and rets.std() > 0:
        out["sharpe"] = float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS))
        downside = rets[rets < 0]
        out["sortino"] = float(
            rets.mean() / downside.std() * np.sqrt(TRADING_DAYS)
        ) if len(downside) > 1 and downside.std() > 0 else float("nan")
    else:
        out["sharpe"] = out["sortino"] = float("nan")

    mdd, mdd_at = max_drawdown(eq)
    out["max_dd_pct"] = mdd
    out["max_dd_at"] = str(mdd_at) if mdd_at is not None else ""
    out["calmar"] = float(out["cagr_pct"] / abs(mdd)) if mdd < 0 else float("nan")

    if len(tr) == 0:
        return out

    wins = tr[tr["pnl"] > 0]
    losses = tr[tr["pnl"] <= 0]
    gross_win = float(wins["pnl"].sum())
    gross_loss = float(-losses["pnl"].sum())
    out["win_rate_pct"] = float(len(wins) / len(tr) * 100.0)
    out["profit_factor"] = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")
    out["avg_win"] = float(wins["pnl"].mean()) if len(wins) else 0.0
    out["avg_loss"] = float(losses["pnl"].mean()) if len(losses) else 0.0
    out["expectancy"] = float(tr["pnl"].mean())
    out["avg_bars_held"] = float(tr["bars_held"].mean())
    out["total_costs"] = float(tr["cost"].sum())
    out["cost_pct_of_gross"] = (
        float(tr["cost"].sum() / abs(tr["gross"].sum()) * 100.0) if tr["gross"].sum() != 0 else float("nan")
    )
    out["trades_per_week"] = float(len(tr) / (days / 7.0))
    out["max_consec_losses"] = int(_max_streak(tr["pnl"] <= 0))
    return out


def _max_streak(flags: pd.Series) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def breakdowns(res: dict) -> dict[str, pd.DataFrame]:
    """Slice the trade list the ways that actually tell you if the edge is real."""
    tr = res["trades"]
    if tr.empty:
        return {}
    t = tr.copy()
    tpe = pd.DatetimeIndex(t["entry_ts"]).tz_convert("Asia/Taipei")
    t["month"] = tpe.strftime("%Y-%m")
    t["tpe_hour"] = tpe.hour
    t["dow"] = tpe.dayofweek

    def agg(col: str) -> pd.DataFrame:
        g = t.groupby(col).agg(
            trades=("pnl", "size"),
            pnl=("pnl", "sum"),
            win_rate=("pnl", lambda s: (s > 0).mean() * 100.0),
            avg=("pnl", "mean"),
        )
        return g.round(2)

    return {
        "by_month": agg("month"),
        "by_hour": agg("tpe_hour"),
        "by_dow": agg("dow"),
        "by_side": agg("side"),
        "by_reason": agg("reason"),
    }
