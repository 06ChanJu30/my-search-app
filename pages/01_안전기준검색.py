import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import numpy as np
import gdown 
from datetime import datetime

# 1. 페이지 설정은 무조건 최상단에 위치
st.set_page_config(page_title="안전보건 기준 검색", layout="centered")

# 2. 메인으로 돌아가기 버튼
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# 3. 경로 및 변수 설정
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOGLE_DRIVE_URL = "https://drive.google.com/uc?id=1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ"

PDF_FILE_NAME = os.path.join(current_dir, "standard.pdf")
DATA_JSON_NAME = os.path.join(current_dir, "standards_data.json")
INDEX_FILE_NAME = os.path.join(current_dir, "toc.index") 
SYNONYM_FILE_NAME = os.path.join(current_dir, "synonyms.json")
LOG_FILE_NAME = os.path.join(current_dir, "search_log.csv") 

# AI 검색 모듈 로드
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    st.error("⚠️ AI 검색 모듈이 설치되지 않았습니다.")
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
    if not data: 
        return None
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
        return None

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

@st.cache_resource
def download_pdf_from_gdrive(url, output_path):
    if os.path.exists(output_path):
        return output_path
    try:
        with st.spinner("데이터 파일 다운로드 중..."):
            gdown.download(url, output_path, quiet=False)
        return output_path
    except Exception as e:
        st.error(f"파일 다운로드 실패: {e}")
        return None

# --- 메인 실행 로직 ---

st.title("👷 안전보건 기준(OPS) 검색엔진")

# PDF 다운로드
pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
if not pdf_path or not os.path.exists(pdf_path): 
    st.error("PDF 파일을 불러올 수 없습니다. 구글 드라이브 공유 설정을 확인하세요.")
    st.stop()

df = load_data(DATA_JSON_NAME)
if df is None:
    st.warning("데이터 파일(JSON)을 찾을 수 없습니다.")
    st.stop()

model, index = load_search_engine(INDEX_FILE_NAME)
synonyms = load_synonyms(SYNONYM_FILE_NAME)

# 세션 상태 초기화
if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

def on_search_click():
    if st.session_state.search_query.strip():
        log_search_query(st.session_state.search_query)

def show_full_text(result_item):
    st.session_state.selected_item = result_item
    st.session_state.search_query = ""

def go_to_main():
    st.session_state.selected_item = None
    st.session_state.search_query = ""

# 검색창
query = st.text_input(
    "🔍 검색어를 입력하세요", 
    key="search_query",
    on_change=on_search_click
)

if query:
    st.session_state.selected_item = None 
    final_indices = []
    
    norm_query = normalize_text(query)
    if norm_query in synonyms:
        synonym_ids = synonyms[norm_query]
        final_indices.extend(df[df['id'].isin(synonym_ids)].index.tolist())
    
    normalized_keywords = [normalize_text(k) for k in query.split() if k]
    if normalized_keywords:
        temp_df = df.copy()
        for kw in normalized_keywords:
            temp_df = temp_df[temp_df['search_normalized'].str.contains(kw, na=False)]
        final_indices.extend(temp_df.index.tolist())
    
    if model and index:
        q_emb = model.encode([query])
        _, indices = index.search(np.array(q_emb).astype('float32'), k=5)
        final_indices.extend([i for i in indices[0] if i != -1])
    
    final_indices = list(dict.fromkeys(final_indices))
    results_df = df.iloc[final_indices]

    st.subheader(f"🔍 검색 결과 ({len(results_df)}개)")
    for i, row in results_df.iterrows():
        with st.container(border=True):
            st.markdown(f"### {row['full_title']}")
            if st.button("상세 보기", key=f"btn_{i}"):
                show_full_text(row)
                st.rerun()

elif st.session_state.selected_item is not None:
    item = st.session_state.selected_item
    st.button("← 돌아가기", on_click=go_to_main)
    st.markdown(f"## {item['full_title']}")
    
    p_start = int(item['page_start'])
    p_end = int(item.get('page_end', p_start))
    
    for p in range(p_start, p_end + 1):
        img = render_pdf_page(pdf_path, p)
        if img:
            st.image(img, use_container_width=True)
        st.divider()

else:
    st.subheader("📑 기준집 목차")
    if 'category' not in df.columns:
        df['category'] = df['id'].apply(lambda x: x.split('-')[0] if '-' in str(x) else "기타")
    
    for cat in sorted(df['category'].unique()):
        with st.expander(f"📁 {cat}"):
            cat_items = df[df['category'] == cat]
            for _, row in cat_items.iterrows():
                if st.button(row['full_title'], key=f"list_{row['id']}", use_container_width=True):
                    show_full_text(row)
                    st.rerun()

# 하단 정보
st.divider()
st.caption("📄 문의: 안전팀 백찬주 대리 (010-2528-5706)")
