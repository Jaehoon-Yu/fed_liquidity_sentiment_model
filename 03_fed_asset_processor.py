import os
import re
import time
import pandas as pd
import numpy as np
from datetime import datetime

# ===== 사용자 설정 =====
SOURCE_PATH = r"C:\Users\USER\Desktop\WALCL.csv"   # WALCL.csv의 실제 경로
START_DATE  = "2017-01-01"                         # 시작일
# ======================

def read_walcl_csv_robust(path: str) -> pd.DataFrame:
    """
    FRED에서 받은 다양한 형태의 WALCL CSV를 강건하게 읽어
    (date, value[Millions of $]) 두 열로 표준화해 반환.
    """
    if not os.path.exists(path):
        raise SystemExit(f"CSV 파일이 존재하지 않습니다: {path}")

    # 구분자 자동 감지 + 문제 행 스킵
    df = pd.read_csv(path, engine="python", sep=None, on_bad_lines="skip")

    # 열 이름 표준화
    df.columns = [re.sub(r"\s+", "_", c.strip()).lower() for c in df.columns]

    # 날짜 열 후보 탐색
    preferred_date_names = [
        "date", "observation_date", "observationdate",
        "observation-date", "observation_date_time"
    ]
    date_col = None
    for name in preferred_date_names:
        if name in df.columns:
            date_col = name
            break

    if date_col is None:
        # 통계적으로 날짜로 보이는 열 찾기
        candidates = []
        for c in df.columns:
            sample = df[c].astype(str).head(200)
            parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
            if parsed.notna().mean() > 0.6:
                candidates.append(c)
        if candidates:
            date_col = candidates[0]

    if date_col is None:
        raise SystemExit(f"날짜 열을 찾지 못했습니다. 열 목록: {df.columns.tolist()}")

    # 값 열 후보 탐색
    preferred_value_names = ["value", "walcl", "observation_value", "obs_value"]
    value_col = None
    for name in preferred_value_names:
        if name in df.columns:
            value_col = name
            break

    if value_col is None:
        # 숫자형 비율이 높은 열을 값열로 추정
        numeric_cands = []
        for c in df.columns:
            if c == date_col:
                continue
            s = pd.to_numeric(df[c].replace({".": np.nan}), errors="coerce")
            if s.notna().mean() > 0.9:
                numeric_cands.append((c, s.notna().mean()))
        if numeric_cands:
            value_col = sorted(numeric_cands, key=lambda x: x[1], reverse=True)[0][0]

    if value_col is None:
        raise SystemExit(f"값 열을 찾지 못했습니다. 열 목록: {df.columns.tolist()}")

    # 정리
    out = df[[date_col, value_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce", infer_datetime_format=True)
    out[value_col] = pd.to_numeric(out[value_col].replace({".": np.nan}), errors="coerce")
    out = out.dropna(subset=[date_col, value_col])
    out = out[out[date_col] >= pd.Timestamp(START_DATE)].copy()

    out = out.rename(columns={date_col: "date", value_col: "value"})
    # WALCL 단위는 Millions of dollars
    return out[["date", "value"]]

def to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    주간 시계열 → 월말 기준 평균 집계.
    monthly_avg_assets: Millions of $
    monthly_avg_assets_million: Trillions of $
    """
    monthly = (
        df.set_index("date")["value"]
          .resample("M")
          .mean()
          .to_frame("monthly_avg_assets")
          .dropna()
    )
    monthly["monthly_avg_assets_million"] = (monthly["monthly_avg_assets"] / 1_000_000).round(2)
    monthly = monthly.reset_index()
    monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
    return monthly

def safe_to_csv(df: pd.DataFrame, out_path: str, max_retries: int = 1) -> str:
    """
    CSV 저장 시 PermissionError(파일 잠금 등) 발생하면
    타임스탬프를 붙인 대체 파일명으로 저장하여 우회.
    반환값: 실제 저장된 경로
    """
    try:
        df.to_csv(out_path, index=False)
        return out_path
    except PermissionError:
        # 잠금 상태일 가능성: 다른 이름으로 저장
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(out_path)
        alt_path = f"{base}_{ts}{ext}"
        df.to_csv(alt_path, index=False)
        print(f"⚠️ 기본 파일이 잠겨 있어 대체 파일로 저장했습니다 → {alt_path}")
        return alt_path

def main():
    print(f"📄 소스 파일: {SOURCE_PATH}")
    df_raw = read_walcl_csv_robust(SOURCE_PATH)
    monthly = to_monthly(df_raw)

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    out_path = os.path.join(desktop, "monthly_fed_assets.csv")
    saved_path = safe_to_csv(monthly, out_path)

    print(f"✅ 저장 완료: {saved_path}")
    print(monthly.head(10))

if __name__ == "__main__":
    main()
