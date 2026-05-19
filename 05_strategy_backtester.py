import os
import pandas as pd
import numpy as np
from datetime import datetime

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
signal_path = os.path.join(desktop, "signal_with_change.csv")
market_path = os.path.join(desktop, "spy_monthly_returns.csv")  # 또는 spx_monthly_returns.csv
output_path = os.path.join(desktop, "backtest_result.csv")

signal_df = pd.read_csv(signal_path)
mkt_df    = pd.read_csv(market_path)

signal_df.columns = [c.strip().lower().replace(" ", "_") for c in signal_df.columns]
mkt_df.columns    = [c.strip().lower().replace(" ", "_") for c in mkt_df.columns]

# 날짜
signal_df["date"] = pd.to_datetime(signal_df["date"]).dt.to_period("M").dt.to_timestamp()
mkt_df["date"]    = pd.to_datetime(mkt_df["date"]).dt.to_period("M").dt.to_timestamp()

# 시장 수익률 컬럼 자동
ret_candidates = ["spx_return", "spy_return", "return", "mkt_return"]
ret_col = next((c for c in ret_candidates if c in mkt_df.columns), None)
if ret_col is None:
    raise SystemExit(f"시장 수익률 컬럼을 찾지 못했습니다. 실제: {list(mkt_df.columns)}")

mkt_df = mkt_df[["date", ret_col]].rename(columns={ret_col: "mkt_return"})
mkt_df["mkt_return"] = pd.to_numeric(mkt_df["mkt_return"], errors="coerce")

df = pd.merge(signal_df, mkt_df, on="date", how="inner").sort_values("date").reset_index(drop=True)

df["signal"] = pd.to_numeric(df["signal"], errors="coerce").fillna(0).astype(int)

# 정렬 규칙
# 신호는 "다음 달"에 적용되도록 1개월 시프트: next_position_signal = signal.shift(1)
# 초기 포지션은 1(롱)로 시작. 이후 신호가 -1이면 0(현금), 1이면 1(롱), 0이면 이전 유지.
sig_prev = df["signal"].shift(1)

position = []
state = 1  # 초기 롱
for s in sig_prev:
    if pd.isna(s):
        # 첫 달: 초기 상태 유지
        position.append(state)
        continue
    if s == 1:
        state = 1
    elif s == -1:
        state = 0
    # s == 0이면 유지
    position.append(state)

df["position"] = position

# 전략 수익률: 해당 달 수익률 * 해당 달 포지션
df["strategy_return"] = df["position"] * df["mkt_return"]

# 누적 수익률
df["cumulative_strategy"] = (1 + df["strategy_return"].fillna(0)).cumprod()
df["cumulative_market"]   = (1 + df["mkt_return"].fillna(0)).cumprod()

# 반올림
df["strategy_return"] = df["strategy_return"].round(6)
df["mkt_return"]      = df["mkt_return"].round(6)
df["cumulative_strategy"] = df["cumulative_strategy"].round(6)
df["cumulative_market"]   = df["cumulative_market"].round(6)

def safe_save(dataframe, path):
    try:
        dataframe.to_csv(path, index=False)
        print(f"백테스트 결과 저장 완료: {path}")
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = path.replace(".csv", f"_{ts}.csv")
        dataframe.to_csv(alt, index=False)
        print(f"파일이 열려 있어 다른 이름으로 저장했습니다: {alt}")

safe_save(df, output_path)

print(df[["date","signal","position","mkt_return","strategy_return","cumulative_strategy","cumulative_market"]].head(12))
