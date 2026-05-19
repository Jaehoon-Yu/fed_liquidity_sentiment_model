import os
import re
import math
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

# ===== 설정 =====
MODEL_NAME = "ProsusAI/finbert"   # 금융 도메인용
REVISION   = "main"
USE_GPU = torch.cuda.is_available()
DEVICE = 0 if USE_GPU else -1

# 모델/토크나이저 명시 로드 (경고 제거)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=REVISION)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, revision=REVISION)

# 파이프라인 준비 (배치 추론용)
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model=model,
    tokenizer=tokenizer,
    device=DEVICE,
    truncation=True
)

# 바탕화면/beigebook 폴더
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
folder_path = os.path.join(desktop_path, "beigebook")  # 여기에 txt들

# 간단한 문장 분할기 (마침표/물음표/느낌표 기준, 너무 짧은 조각은 붙이기)
def split_into_sentences(text):
    # 줄바꿈 정리
    text = re.sub(r'\s+', ' ', text).strip()
    # 문장 분리
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    # 너무 짧은 문장 합치기
    merged = []
    buf = ""
    for s in sents:
        if len(s) < 40:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(s.strip())
    if buf:
        merged.append(buf)
    return [s for s in merged if s]

# 토큰 길이 제한으로 청크 만들기 (모델 max_length 고려)
def chunk_by_tokens(sentences, max_length=256, stride=0):
    chunks = []
    cur = []
    cur_len = 0
    for s in sentences:
        tokens = tokenizer.encode(s, add_special_tokens=False)
        if cur_len + len(tokens) > max_length:
            if cur:
                chunks.append(" ".join(cur))
            cur = [s]
            cur_len = len(tokens)
        else:
            cur.append(s)
            cur_len += len(tokens)
    if cur:
        chunks.append(" ".join(cur))
    return chunks

# 라벨 → 0~200 스케일 (중립=100)
# ProsusAI/finbert 라벨: 'positive','negative','neutral'
def to_scaled_score(label, score):
    label = label.lower()
    if label == "positive":
        # score∈[0,1], 0.5=중립 근처로 보고 선형 스케일
        return 100 + 100 * (score - 0.5)
    elif label == "negative":
        return 100 - 100 * (score - 0.5)
    elif label == "neutral":
        return 100.0
    else:
        return 100.0

records = []

for filename in sorted(os.listdir(folder_path)):
    if filename.startswith("beigebook_") and filename.endswith(".txt"):
        with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as f:
            text = f.read()

        # 문장 분리 → 토큰 기준 청크 (최대 30개 정도만 사용해도 충분)
        sentences = split_into_sentences(text)
        chunks = chunk_by_tokens(sentences, max_length=256)
        chunks = chunks[:30]

        # 배치 추론 (속도↑)
        results = sentiment_analyzer(chunks, batch_size=16)
        scaled = []
        for r in results:
            # FinBERT는 dict 또는 list 형태가 올 수 있음
            if isinstance(r, list) and len(r) > 0:
                r = r[0]
            label = r["label"]
            score = float(r["score"])
            scaled.append(to_scaled_score(label, score))

        avg_score = round(sum(scaled) / len(scaled), 2) if scaled else 100.0
        period = filename.replace("beigebook_", "").replace(".txt", "")
        date = f"{period[:4]}-{period[4:]}-01"

        records.append({
            "date": date,
            "sentiment_score": avg_score,
            "chunks_used": len(scaled)
        })

# DataFrame 저장
df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

output_path = os.path.join(desktop_path, "beigebook_sentiment_score_scaled.csv")
df.to_csv(output_path, index=False)
print(f"감정 점수 저장 완료: {output_path}")

# 디바이스 정보 출력
print("DEVICE:", "cuda:0" if USE_GPU else "cpu")
