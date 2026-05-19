import os
import re
import pandas as pd
import numpy as np

# === 파일 경로 ===
desktop = os.path.join(os.path.expanduser("~"), "Desktop")
input_file = os.path.join(desktop, "merged_sentiment_fed_assets_fixed.csv")
output_file = os.path.join(desktop, "signal_with_change.csv")

# === CSV 읽기 ===
df = pd.read_csv(input_file)
df.columns = [re.sub(r"\s+", "_", c.strip().lower()) for c in df.columns]

# === 컬럼 이름 변형 대응 ===
def find_col(possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    raise ValueError(f"다음 중 어떤 열도 찾을 수 없음: {possible_names}")

date_col   = find_col(["date_sentiment", "date", "date_senti", "date_sent"])
sent_col   = find_col(["sentiment_score", "sentiment"])
chunk_col  = find_col(["chunks_used", "chunks_us"])
asset_date = find_col(["date_assets", "date_asset"])
asset_col  = find_col(["monthly_avg_assets", "monthly_a"])
asset_mil  = find_col(["monthly_avg_assets_million", "monthly_a_million"])

# === 필요한 열만 추출 ===
df = df[[date_col, sent_col, chunk_col, asset_date, asset_col, asset_mil]].copy()
df.columns = [
    "date", "sentiment_score", "chunks_used",
    "date_assets", "monthly_avg_assets", "monthly_avg_assets_million"
]

# === 형식 정리 ===
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["date_assets"] = pd.to_datetime(df["date_assets"], errors="coerce")
df = df.dropna(subset=["date", "date_assets"]).sort_values("date").reset_index(drop=True)

df["sentiment_score"] = pd.to_numeric(df["sentiment_score"], errors="coerce")
df["monthly_avg_assets"] = pd.to_numeric(df["monthly_avg_assets"], errors="coerce")

# === 변화율 계산 ===
df["sentiment_change"] = df["sentiment_score"].pct_change()
df["liquidity_change"] = df["monthly_avg_assets"].pct_change()

# === 시그널 계산 ===
def calc_signal(row):
    sc = row["sentiment_change"]
    lc = row["liquidity_change"]
    if pd.isna(sc) or pd.isna(lc):
        return 0
    if lc == 0:
        if sc > 0:
            return -1
        elif sc < 0:
            return 1
        else:
            return 0
    return -1 if np.sign(sc) == np.sign(lc) else 1

df["signal"] = df.apply(calc_signal, axis=1)

# === 포맷팅 ===
df["date"] = df["date"].dt.strftime("%Y-%m-%d")
df["date_assets"] = df["date_assets"].dt.strftime("%Y-%m-%d")
df["sentiment_change"] = df["sentiment_change"].round(8)
df["liquidity_change"] = df["liquidity_change"].round(8)

# === 저장 ===
df.to_csv(output_file, index=False, encoding="utf-8")
print(f"✅ 저장 완료: {output_file}")
print(df.head(10))
