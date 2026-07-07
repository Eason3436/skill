"""Run the backtest and emit results.json + REPORT.md."""
import json
from engine import load_1h, resample, backtest, CONFIG

INST = "TSM-USDT-SWAP"


def main():
    df1h = load_1h(f"backtest/data_{INST}_1H.json")
    results = []
    for hours, k in CONFIG:
        df = resample(df1h, hours)
        r = backtest(df, k)
        results.append((hours, k, r))

    # results.json
    dump = {
        "instrument": INST,
        "exchange": "OKX",
        "base_data": "1H candles resampled to each timeframe",
        "band": "Bollinger: SMA(20) +/- k*stddev(20, population)",
        "rules": "long-only; enter at close <= lower band; exit at close >= upper band; NO stop loss",
        "sizing": "100% equity per trade, 1x, no fees",
        "period": {"from": str(df1h.index[0]), "to": str(df1h.index[-1])},
        "configs": [],
    }
    for hours, k, r in results:
        dump["configs"].append({
            "timeframe": f"{hours}H",
            "band_k": k,
            "bars": r["bars"],
            "n_trades": r["n_trades"],
            "win_rate": None if r["n_trades"] == 0 else round(r["win_rate"], 4),
            "total_return_pct": round(r["total_return"] * 100, 2),
            "max_drawdown_pct": round(r["max_drawdown"] * 100, 2),
            "open_at_end": bool(r["open_at_end"]),
            "trades": [
                {"entry": round(e, 2), "exit": round(x, 2),
                 "ret_pct": round(rr * 100, 2)}
                for (e, x, rr) in r["trades"]
            ],
        })
    with open("backtest/results.json", "w") as f:
        json.dump(dump, f, indent=2)

    # REPORT.md
    lines = []
    lines.append(f"# TSM (`{INST}`) Bollinger 均值回歸策略回測\n")
    lines.append(f"- **交易所**：OKX（{INST} 永續合約，tokenized 美股 TSM）")
    lines.append(f"- **資料區間**：{df1h.index[0]} → {df1h.index[-1]}（上市以來全部可得資料）")
    lines.append("- **基礎資料**：1H K 線，重採樣為各週期（OKX 無原生 3H/8H，故由 1H 合成，已對齊 UTC 並與原生 2H 校驗一致）")
    lines.append("- **軌道**：布林通道，中軌 = SMA(20)，上/下軌 = 中軌 ± k×標準差(20)")
    lines.append("- **規則**：只做多；收盤 ≤ 下軌時買入，收盤 ≥ 上軌時賣出；**不設止損**")
    lines.append("- **部位**：每次全額資金 1 倍、無槓桿、未計手續費；權益逐根 mark-to-market，最大回徹取權益曲線最深回落\n")
    lines.append("## 結果總表\n")
    lines.append("| 週期 | 軌道 | 交易數 | 勝率 | **總收益** | **最大回徹** | 期末是否持倉 |")
    lines.append("|------|------|--------|------|-----------|-------------|--------------|")
    for hours, k, r in results:
        wr = "—" if r["n_trades"] == 0 else f"{r['win_rate']*100:.1f}%"
        lines.append(
            f"| {hours}H | ±{k} | {r['n_trades']} | {wr} | "
            f"**{r['total_return']*100:+.2f}%** | **{r['max_drawdown']*100:.2f}%** | "
            f"{'是' if r['open_at_end'] else '否'} |")
    lines.append("\n## 各週期交易明細\n")
    for hours, k, r in results:
        lines.append(f"### {hours}H（軌道 ±{k}）")
        if not r["trades"]:
            lines.append("_無完成交易_\n")
            continue
        lines.append("| # | 進場價 | 出場價 | 單筆報酬 |")
        lines.append("|---|--------|--------|----------|")
        for i, (e, x, rr) in enumerate(r["trades"], 1):
            lines.append(f"| {i} | {e:.2f} | {x:.2f} | {rr*100:+.2f}% |")
        if r["open_at_end"]:
            lines.append("\n_註：回測結束時仍持有一筆未平倉多單（已計入 mark-to-market 收益與回徹）。_")
        lines.append("")
    lines.append("## 重要假設與限制\n")
    lines.append("- 該合約 2026-03 才上市，全部歷史僅約 4 個月，樣本偏少，統計意義有限。")
    lines.append("- 未計交易手續費、資金費率、滑點；實盤收益會低於此。")
    lines.append("- 進出場以「同一根收盤價」成交（收盤觸軌即成交），略為樂觀。")
    lines.append("- 只做多，未做空；「不設止損」代表持倉期間完全承受回檔直到觸及上軌。")
    with open("backtest/REPORT.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote backtest/results.json and backtest/REPORT.md")
    print("\n".join(lines[8:22]))


if __name__ == "__main__":
    main()
