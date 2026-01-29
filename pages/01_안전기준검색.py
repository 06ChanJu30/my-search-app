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

# [수정 1] set_page_config는 무조건 맨 위에 있어야 에러가 안 납니다!
st.set_page_config(page_title="안전보건 기준 검색", layout="centered")

# [수정 2] 홈 버튼 추가 (설정 바로 아래에 위치)
st.page_link("Home.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# [수정 3] 경로 설정 (pages 폴더가 아닌, 최상위 폴더를 기준으로 잡기 위함)
# 현재 파일(01_...py)의 부모 폴더(pages)의 부모 폴더(루트)를 찾습니다.
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- 설정 (파일 이름 및 경로) ---
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"

# 파일들이 'pages' 폴더가 아니라 프로젝트 최상위 폴더에 저장되도록 경로 수정
PDF_FILE_NAME = os.path.join(current_dir, "standard.pdf")
DATA_JSON_NAME = os.path.join(current_dir, "standards_data.json")
INDEX_FILE_NAME = os.path.join(current_dir, "toc.index") 
SYNONYM_FILE_NAME = os.path.join(current_dir, "synonyms.json")
LOG_FILE_NAME = os.path.join(current_dir, "search_log.csv") 
# ---

# AI 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    st.error("⚠️ AI 검색 모듈이 설치되지 않았습니다.")
    st.info("터미널에 다음 명령어를 입력해 설치해주세요: pip install sentence-transformers faiss-cpu pymupdf gdown")
    st.stop()

# --- 함수 정의 ---

def log_search_query(query):
    """검색어를 CSV 파일에 저장합니다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not os.path.exists(LOG_FILE_NAME):
        with open(LOG_FILE_NAME, "w", encoding="utf-8") as f:
            f.write("timestamp,query\n")
            
    clean_query = query.replace(",", " ") 
    with open(LOG_FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{timestamp},{clean_query}\n")

def load_search_stats():
    """저장된 검색 기록을 불러와 통계를 냅니다."""
    if not os.path.exists(LOG_FILE_NAME):
        return pd.DataFrame(columns=["검색어", "횟수"])
    
    try:
        df_log = pd.read_csv(LOG_FILE_NAME)
        if df_log.empty:
            return pd.DataFrame(columns=["검색어", "횟수"])
            
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
        # 동의어 파일 없으면 그냥 빈 딕셔너리 반환 (에러 안 띄움)
        return {}

@st.cache_data
def render_pdf_page(pdf_path, page_num, dpi=150):
    try:
        doc = fitz.open(pdf_path)
        # 페이지 번호가 범위를 벗어나지 않도록 체크
        if page_num < 1 or page_num > len(doc):
             return None
        page = doc.load_page(page_num - 1)
        pix = page.get_pixmap(dpi=dpi)
        doc.close()
        img_bytes = pix.tobytes("png")
        return img_bytes
    except Exception as e:
        st.error(f"PDF 렌더링 오류 (페이지: {page_num}): {e}")
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
        with st.spinner(f"데이터 파일 다운로드 중... ({os.path.basename(output_path)})"):
            gdown.download(url, output_path, quiet=False, fuzzy=True)
        return output_path
    except Exception as e:
        st.error(f"파일 다운로드 실패: {e}")
        return None

# --- 실행 로직 ---

st.title("👷 안전보건 기준(OPS) 검색엔진")

# 1. 필수 파일 다운로드 및 로드
pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
if not pdf_path: 
    st.error("PDF 파일을 찾을 수 없습니다.")
    st.stop()

# JSON 데이터 로드
df = load_data(DATA_JSON_NAME)
if df is None:
    st.warning(f"데이터 파일({os.path.basename(DATA_JSON_NAME)})이 없습니다. 구글 드라이브 다운로드를 확인하세요.")
    st.stop()

# 검색 엔진 로드
model, index = load_search_engine(INDEX_FILE_NAME)
if model is None or index is None:
    st.warning("AI 검색 인덱스 파일이 없습니다. (키워드 검색만 가능합니다)")
    # AI 모델이 없어도 키워드 검색은 되도록 통과시킬 수도 있지만, 원본 로직 유지
    st.stop()

synonyms = load_synonyms(SYNONYM_FILE_NAME)

# 2. 세션 상태 초기화
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
    st.rerun()

def go_to_main():
    st.session_state.selected_item = None
    st.session_state.search_query = ""
    st.rerun()

# 3. 메인 화면 구성
query = st.text_input(
    "🔍 검색어를 입력하세요 (예: '용접', '추락', '고소 작업대')", 
    key="search_query",
    on_change=on_search_click
)

if query:
    st.session_state.selected_item = None 
    final_indices = []
    
    # 동의어 처리
    norm_query = normalize_text(query)
    if norm_query in synonyms:
        synonym_ids = synonyms[norm_query]
        synonym_df_indices = df[df['id'].isin(synonym_ids)].index
        final_indices.extend(synonym_df_indices)
    
    # 키워드 검색
    normalized_keywords = [normalize_text(k) for k in query.split() if k]
    keyword_results = df.copy()
    if normalized_keywords:
        for kw in normalized_keywords:
            keyword_results = keyword_results[keyword_results['search_normalized'].str.contains(kw, na=False)]
    
    keyword_indices = set(keyword_results.index)
    for idx in keyword_indices:
        if idx not in final_indices:
            final_indices.append(idx)
    
    # AI 의미 검색
    if model and index:
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
            st.image(img_bytes, use_container_width=True) # width 옵션 최신화
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
        if 'category' not in df.columns:
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
                file_name="standard.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    except FileNotFoundError:
        st.error(f"파일을 찾을 수 없습니다.")


# --- 하단 정보 및 통계 ---
st.divider()
st.caption("📄 기준집 관련 문의사항: 안전팀 (02-0000-0000)")

with st.sidebar.expander("📊 검색 통계 보기 (관리자용)"):
    stats_df = load_search_stats()
    if not stats_df.empty:
        st.write("🔥 **많이 검색된 키워드 TOP 5**")
        top_5 = stats_df.head(5).set_index('검색어')
        st.bar_chart(top_5)
        st.write("📋 **전체 검색 기록**")
        st.dataframe(stats_df, hide_index=True)
    else:
        st.info("아직 검색 기록이 없습니다.")
