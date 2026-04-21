import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import numpy as np
import gdown 
from datetime import datetime
from collections import Counter

# [수정 1] set_page_config는 최상단 유지
st.set_page_config(page_title="안전보건 기준 검색", layout="centered")

# [수정 2] 홈 버튼 및 경로 설정
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 설정 (URL 수정) ---
# 구글 드라이브 링크는 /view 형식보다 /uc?id= 형식이 다운로드에 훨씬 안정적입니다.
GOOGLE_DRIVE_URL = "https://drive.google.com/uc?id=1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ"

PDF_FILE_NAME = os.path.join(current_dir, "standard.pdf")
DATA_JSON_NAME = os.path.join(current_dir, "standards_data.json")
INDEX_FILE_NAME = os.path.join(current_dir, "toc.index") 
SYNONYM_FILE_NAME = os.path.join(current_dir, "synonyms.json")
LOG_FILE_NAME = os.path.join(current_dir, "search_log.csv") 

# AI 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    st.error("⚠️ AI 검색 모듈이 설치되지 않았습니다.")
    st.info("pip install sentence-transformers faiss-cpu pymupdf gdown")
    st.stop()

# --- 함수 정의 ---

def log_search_query(query):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(LOG_FILE_NAME):
        with open(LOG_FILE_NAME, "w", encoding="utf-8") as f:
            f.write("timestamp,query\n")
    clean_query = query.replace(",", " ") 
    with open(LOG_FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{timestamp},{clean_query}\n")

def load_search_stats():
    if not os.path.exists(LOG_FILE_NAME):
        return pd.DataFrame(columns=["검색어", "횟수"])
    try:
        df_log = pd.read_csv(LOG_FILE_NAME)
        if df_log.empty:
            return pd.DataFrame(columns=["검색어", "횟수"])
        counts = df_log['query'].value_counts().reset_index()
        counts.columns = ['검색어', '횟수']
        return counts
    except:
        return pd.DataFrame(columns=["검색어", "횟수"])

@st.cache_resource
def load_data(json_path):
    if not os.path.exists(json_path):
        return None
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not data: return None
    df = pd.DataFrame(data)
    df['full_title'] = df.apply(lambda row: f"{row.get('id', 'ID없음')}: {row.get('title', '제목없음')}", axis=1)
    return df

@st.cache_resource
def load_search_engine(index_path):
    if not os.path.exists(index_path):
        return None, None
    try:
        model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        index = faiss.read_index(index_path)
        return model, index
    except Exception as e:
        st.error(f"AI 검색 엔진 로드 실패: {e}")
        return None, None

@st.cache_resource
def load_synonyms(synonym_path):
    if not os.path.exists(synonym_path):
        return {}
    try:
        with open(synonym_path, 'r', encoding='utf-8') as f:
            synonyms = json.load(f)
        return {normalize_text(k): v for k, v in synonyms.items()}
    except:
        return {}

@st.cache_data
def render_pdf_page(pdf_path, page_num, dpi=150):
    try:
        doc = fitz.open(pdf_path)
        if page_num < 1 or page_num > len(doc):
             return None
        page = doc.load_page(page_num - 1)
        pix = page.get_pixmap(dpi=dpi)
        doc.close()
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"PDF 렌더링 오류: {e}")
        return None

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

# [해결 핵심] gdown의 fuzzy 옵션 제거 및 URL 처리
@st.cache_resource
def download_pdf_from_gdrive(url, output_path):
    if os.path.exists(output_path):
        return output_path
    try:
        with st.spinner(f"데이터 파일 다운로드 중..."):
            # fuzzy=True 옵션을 제거하여 에러 수정
            gdown.download(
