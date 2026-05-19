import os
import re
import time
import sys
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 설정
BASE = "https://www.federalreserve.gov"
PUBS = f"{BASE}/monetarypolicy/publications/beige-book-default.htm"
HEADERS = {"User-Agent": "Mozilla/5.0"}
YEAR_TARGET = "2025"          
SAVE_DIR = "beigebook_2025"   
KEEP_PDF = True               # PDF 보관? (false, PDF 삭제)

os.makedirs(SAVE_DIR, exist_ok=True)

# 패키지자동설치
def ensure_import(mod_name, pip_name=None):
    """
    mod_name: import할 모듈명 (ex: 'pdfminer.high_level')
    pip_name: pip 설치 패키지명 (ex: 'pdfminer.six'); None이면 mod_name 그대로 사용
    """
    try:
        __import__(mod_name.split('.')[0])
        return True
    except ImportError:
        pkg = pip_name or mod_name
        try:
            print(f"'{pkg}' 설치합니다")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            __import__(mod_name.split('.')[0])
            return True
        except Exception as e:
            print(f"NO '{pkg}' 설치 실패: {e}")
            return False

def download_binary(url, path, retries=2, backoff=1.5):
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            return True
        except Exception as e:
            if i == retries:
                print(f"NO 다운로드 실패: {url} → {e}")
                return False
            time.sleep(backoff ** i)

def html_to_text(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text

def clean_text(txt: str) -> str:
    lines = txt.splitlines()
    drop_patterns = [
        r"^\s*The Fed - Monetary Policy: Beige Book",
        r"^\s*An official website of the United States Government",
        r"^\s*Back to (Home|Top)",
        r"^\s*Last Update:",
        r"^\s*Board of Governors\s*of the",
        r"^\s*Subscribe to (RSS|Email)",
        r"^\s*Website Policies", r"^\s*Privacy Program", r"^\s*Accessibility",
        r"^\s*20th Street and Constitution Avenue", r"^\s*Home\s*$",
        r"^\s*Sections\s*$", r"^\s*Search\s*$",
    ]
    drop_re = [re.compile(p, re.IGNORECASE) for p in drop_patterns]
    kept = []
    for ln in lines:
        if any(p.search(ln) for p in drop_re):
            continue
        kept.append(ln)
    out, prev_blank = [], False
    for ln in kept:
        blank = (ln.strip() == "")
        if blank and prev_blank:
            continue
        out.append(ln)
        prev_blank = blank
    return "\n".join(out).strip()
def pdf_to_text(pdf_path) -> str:
    if ensure_import("pdfminer.high_level", "pdfminer.six"):
        from pdfminer.high_level import extract_text
        try:
            return extract_text(pdf_path)
        except Exception as e:
            print(" pdfminer.six 추출 실패, pypdf로:", e)
    if ensure_import("pypdf", "pypdf"):
        import pypdf
        txt_parts = []
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for p in reader.pages:
                txt_parts.append(p.extract_text() or "")
        return "\n".join(txt_parts)
    # 최종
    raise RuntimeError("PDF 텍스트 추출 설치 실패")

# 2025년 수집
r = requests.get(PUBS, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

pat_pdf  = re.compile(r"/monetarypolicy/files/BeigeBook_(\d{8})\.pdf", re.IGNORECASE)
pat_html = re.compile(r"/monetarypolicy/beigebook(\d{6})\.htm", re.IGNORECASE)

pdf_by_month  = {}  # YYYYMM → (YYYYMMDD, url)
html_by_month = {}  # YYYYMM → url

for a in soup.find_all("a", href=True):
    href = a["href"]

    m_pdf = pat_pdf.search(href)
    if m_pdf and href.startswith("/monetarypolicy/"):
        yyyymmdd = m_pdf.group(1)
        if yyyymmdd.startswith(YEAR_TARGET):
            yyyymm = yyyymmdd[:6]
            old = pdf_by_month.get(yyyymm, ("00000000", ""))
            if yyyymmdd > old[0]:
                pdf_by_month[yyyymm] = (yyyymmdd, urljoin(PUBS, href))

    m_html = pat_html.search(href)
    if m_html and href.startswith("/monetarypolicy/"):
        yyyymm = m_html.group(1)
        if yyyymm.startswith(YEAR_TARGET):
            html_by_month[yyyymm] = urljoin(PUBS, href)

months = sorted(set(pdf_by_month.keys()).union(html_by_month.keys()))
print("대상 월:", months)

# 각 월HTML
summary = []
for yyyymm in months:
    print(f"\n=== {yyyymm} 처리중 ===")
    txt_name = os.path.join(SAVE_DIR, f"beigebook_{yyyymm}.txt")

    if yyyymm in html_by_month:
        try:
            raw = html_to_text(html_by_month[yyyymm])
            cleaned = clean_text(raw)
            with open(txt_name, "w", encoding="utf-8") as f:
                f.write(cleaned or raw)
            print(f" HTML -> TXT 저장 완료: {txt_name}")
        except Exception as e:
            print(f" HTML -> TXT 실패 ({yyyymm}): {e}")
            # HTML 실패 시
            if yyyymm in pdf_by_month:
                yyyymmdd, pdf_url = pdf_by_month[yyyymm]
                pdf_path = os.path.join(SAVE_DIR, f"BeigeBook_{yyyymmdd}.pdf")
                if not os.path.exists(pdf_path):
                    if not download_binary(pdf_url, pdf_path):
                        print("PDF 다운로드 실패")
                        continue
                try:
                    txt = pdf_to_text(pdf_path)
                    cleaned = clean_text(txt)
                    with open(txt_name, "w", encoding="utf-8") as f:
                        f.write(cleaned or txt)
                    print(f"PDF -> TXT 저장 완료: {txt_name}")
                    if not KEEP_PDF:
                        os.remove(pdf_path)
                except Exception as e2:
                    print(f" PDF -> TXT 실패: {e2}")
    else:
        if yyyymm not in pdf_by_month:
            print(f"{yyyymm}: HTML/PDF 모두 없음")
            continue
        yyyymmdd, pdf_url = pdf_by_month[yyyymm]
        pdf_path = os.path.join(SAVE_DIR, f"BeigeBook_{yyyymmdd}.pdf")
        if not os.path.exists(pdf_path):
            ok = download_binary(pdf_url, pdf_path)
            if not ok:
                print(f"PDF 저장 실패: {pdf_url}")
                continue
            else:
                print(f"PDF 저장: {pdf_path}")
        try:
            txt = pdf_to_text(pdf_path)
            cleaned = clean_text(txt)
            with open(txt_name, "w", encoding="utf-8") as f:
                f.write(cleaned or txt)
            print(f"PDF -> TXT 저장 완료: {txt_name}")
            if not KEEP_PDF:
                os.remove(pdf_path)
        except Exception as e:
            print(f"PDF -> TXT 실패: {e}")

    summary.append({
        "month": yyyymm,
        "txt": os.path.exists(txt_name),
        "html_used": (yyyymm in html_by_month)
    })

# 요약
print("TXT 요약")
for s in summary:
    print(f"{s['month']}: txt={'OK' if s['txt'] else 'FAIL'} | source={'HTML' if s['html_used'] else 'PDF'}")
