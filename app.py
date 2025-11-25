import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import numpy as np
import gdown 
from datetime import datetime # [V21] 시간 기록용
from collections import Counter # [V21] 통계 계산용

# [V21] AI 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    st.error("AI 검색 모듈을 찾을 수 없습니다. (requirements.txt 확인)")
    st.stop()

# --- 설정 ---
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"
PDF_FILE_NAME = "standard.pdf"
DATA_JSON_NAME = "standards_data.json"
INDEX_FILE_NAME = "toc.index" 
SYNONYM_FILE_NAME = "synonyms.json"
LOG_FILE_NAME = "search_log.csv" # [V21] 검색 기록 저장 파일
# ---

# [V21] 검색어 로깅 함수
def log_search_query(query):
    """검색어를 CSV 파일에 저장합니다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 파일이 없으면 헤더 생성
    if not os.path.exists(LOG_FILE_NAME):
        with open(LOG_FILE_NAME, "w", encoding="utf-8") as f:
            f.write("timestamp,query\n")
            
    # 검색어 저장 (콤마 제거 등 전처리)
    clean_query = query.replace(",", " ") 
    with open(LOG_FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{timestamp},{clean_query}\n")

# [V21] 통계 데이터 로드 함수
def load_search_stats():
    """저장된 검색 기록을 불러와 통계를 냅니다."""
    if not os.path.exists(LOG_FILE_NAME):
        return pd.DataFrame(columns=["검색어", "횟수"])
    
    try:
        df_log = pd.read_csv(LOG_FILE_NAME)
        if df_log.empty:
            return pd.DataFrame(columns=["검색어", "횟수"])
            
        # 검색어 빈도 계산
        counts = df_log['query'].value_counts().reset_index()
        counts.columns = ['검색어', '횟수']
        return counts
    except Exception:
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
    except Exception as e:
        st.error(f"'{synonym_path}' 파일 로드 오류: {e}")
        return {}

@st.cache_data
def render_pdf_page(pdf_path, page_num, dpi=150):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num - 1)
        pix = page.get_pixmap(dpi=dpi)
        doc.close()
        img_bytes = pix.tobytes("png")
        return img_bytes
    except Exception as e:
        st.error(f"PDF 페이지 렌더링 오류 (페이지: {page_num}): {e}")
        return None

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

@st.cache_resource
def download_pdf_from_gdrive(url, output_path):
    if os.path.exists(output_path):
        return output_path
    try:
        print(f"'{output_path}' 다운로드 중...")
        gdown.download(url, output_path, quiet=False, fuzzy=True)
        return output_path
    except Exception as e:
        st.error(f"PDF 파일 다운로드 실패: {e}")
        return None

# --- 1. 데이터 로드 ---
pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
if not pdf_path: st.stop()

df = load_data(DATA_JSON_NAME)
if df is None: st.stop()

model, index = load_search_engine(INDEX_FILE_NAME)
if model is None or index is None: st.stop()

synonyms = load_synonyms(SYNONYM_FILE_NAME)

# --- 2. Streamlit UI 구성 ---
st.set_page_config(layout="centered") 
st.title("👷 안전보건 기준(OPS) 검색엔진")

# --- 3. 세션 상태 및 콜백 함수 ---
if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

# [V21] 검색 로깅을 위해 수정된 함수
def on_search_click():
    # 검색어가 있을 때만 로깅
    if st.session_state.search_query.strip():
        log_search_query(st.session_state.search_query)

def show_full_text(result_item):
    st.session_state.selected_item = result_item
    st.session_state.search_query = ""
    st.rerun()

def go_to_main():
    st.session_state.selected_item = None
    st.session_state.search_query = ""
    st.rerun()

# --- 4. 메인 화면 ---
query = st.text_input(
    "🔍 검색어를 입력하세요 (예: '용접', '추락', '고소 작업대')", 
    key="search_query",
    on_change=on_search_click # [V21] 엔터 치면 검색어 저장
)

if query:
    st.session_state.selected_item = None 
    final_indices = []
    
    norm_query = normalize_text(query)
    if norm_query in synonyms:
        synonym_ids = synonyms[norm_query]
        synonym_df_indices = df[df['id'].isin(synonym_ids)].index
        final_indices.extend(synonym_df_indices)
    
    normalized_keywords = [normalize_text(k) for k in query.split() if k]
    keyword_results = df.copy()
    if normalized_keywords:
        for kw in normalized_keywords:
            keyword_results = keyword_results[keyword_results['search_normalized'].str.contains(kw, na=False)]
    
    keyword_indices = set(keyword_results.index)
    for idx in keyword_indices:
        if idx not in final_indices:
            final_indices.append(idx)
    
    q_emb = model.encode([query])
    distances, indices = index.search(np.array(q_emb).astype('float32'), k=5)
    semantic_indices = set(indices[0])
    
    for idx in semantic_indices:
        if idx not in final_indices:
            final_indices.append(idx)
            
    results_df = df.iloc[final_indices]

    st.subheader(f"🔍 '{query}' 검색 결과 ({len(results_df)}개)")
    if len(results_df) == 0:
        st.warning("일치하는 항목을 찾을 수 없습니다.")

    for i, row in results_df.iterrows():
        result = row
        page_start = result['page_start']
        page_end = result.get('page_end', page_start)
        page_range_str = f"{page_start}" if page_start == page_end else f"{page_start}~{page_end}"
        
        with st.container(border=True):
            st.markdown(f"### {result['full_title']} (페이지: {page_range_str})")
            st.button(
                f"PDF 원본 보기: {result['id']}", 
                key=f"search_{i}",
                on_click=show_full_text,
                args=(result,)
            )

elif st.session_state.selected_item is not None:
    item = st.session_state.selected_item
    
    st.button("← 목차로 돌아가기", on_click=go_to_main)
    st.markdown(f"## {item['full_title']}")
    
    page_start = item['page_start']
    page_end = item.get('page_end', page_start)
    st.markdown(f"**페이지 번호:** {page_start} ~ {page_end}")
    st.markdown("---")
    
    for page_to_show in range(page_start, page_end + 1):
        st.subheader(f"📄 PDF 원본 보기 (Page {page_to_show})")
        img_bytes = render_pdf_page(pdf_path, page_to_show)
        if img_bytes:
            st.image(img_bytes, use_column_width=False) 
        st.divider()

else:
    st.subheader("📑 기준집 목차 (카테고리)")
    
    def get_category_name(doc_id):
        if not isinstance(doc_id, str) or '-' not in doc_id:
            return "기타"
        category_prefix = doc_id.split('-')[0]
        if category_prefix == "K" or category_prefix == "양중":
            return "차량계하역운반"
        return category_prefix

    try:
        df['category'] = df['id'].apply(get_category_name)
        categories = sorted(df['category'].unique())
        
        for category in categories:
            with st.expander(f"📁 **{category}**"):
                category_items = df[df['category'] == category]
                for _, row in category_items.sort_values(by='id').iterrows():
                    st.button(
                        f"{row['full_title']}", 
                        key=f"toc_{row['id']}",
                        on_click=show_full_text,
                        args=(row,),
                        use_container_width=True
                    )
    except Exception as e:
        st.error(f"목차를 불러오는 중 오류가 발생했습니다: {e}")

    st.divider()

    try:
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="기준집 PDF 전체 다운로드",
                data=f,
                file_name=PDF_FILE_NAME,
                mime="application/pdf",
                use_container_width=True
            )
    except FileNotFoundError:
        st.error(f"'{pdf_path}' 파일을 찾을 수 없습니다. 앱을 새로고침하세요.")


# --- [V21] 이메일 주소 및 통계 (사이드바) ---
st.divider()
st.caption("📄 기준집 관련 문의사항: 중원엔지니어링 백찬주 대리 king990630@email.com") # 이메일 변경 필요

# [V21] 사이드바에 검색 통계 추가 (관리자용)
with st.sidebar.expander("📊 검색 통계 보기"):
    stats_df = load_search_stats()
    if not stats_df.empty:
        st.write("🔥 **많이 검색된 키워드 TOP 5**")
        # 상위 5개만 차트로 표시
        top_5 = stats_df.head(5).set_index('검색어')
        st.bar_chart(top_5)
        
        st.write("📋 **전체 검색 기록**")
        st.dataframe(stats_df, hide_index=True)
    else:
        st.info("아직 검색 기록이 없습니다.")
