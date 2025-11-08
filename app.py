import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import numpy as np

# [V12] AI 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
except ImportError:
    st.error("AI 검색 모듈을 찾을 수 없습니다. 터미널에서 `pip install sentence-transformers faiss-cpu`를 실행하세요.")
    st.stop()

# --- 설정 ---
PDF_FILE_NAME = "standard.pdf"
DATA_JSON_NAME = "standards_data.json"
INDEX_FILE_NAME = "toc.index" 
SYNONYM_FILE_NAME = "synonyms.json"
# ---

@st.cache_resource
def load_data(json_path):
    """JSON 데이터를 로드하고 DataFrame으로 변환합니다."""
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
    """AI 모델과 FAISS 인덱스를 로드합니다."""
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
    """synonyms.json 파일을 로드합니다."""
    if not os.path.exists(synonym_path):
        st.warning(f"'{synonym_path}' 파일이 없습니다. 유의어 검색 기능이 비활성화됩니다.")
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
    """PDF의 특정 페이지를 이미지로 렌더링합니다."""
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

# --- 1. 데이터 및 검색 엔진 로드 ---
df = load_data(DATA_JSON_NAME)
if df is None:
    st.error(f"'{DATA_JSON_NAME}' 파일을 찾을 수 없습니다. `py -m data_builder`를 먼저 실행하세요.")
    st.stop()

model, index = load_search_engine(INDEX_FILE_NAME)
if model is None or index is None:
    st.error(f"'{INDEX_FILE_NAME}' 파일을 찾을 수 없습니다. `py -m data_builder`를 다시 실행하세요.")
    st.stop()

synonyms = load_synonyms(SYNONYM_FILE_NAME)

# --- 2. Streamlit UI 구성 ---
st.set_page_config(layout="centered") # [V12 수정] 모바일에 최적화된 '중앙 정렬' 레이아웃
st.title("👷 안전보건 기준(OPS) 검색엔진")

# --- 3. 세션 상태 및 콜백 함수 ---
if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

def show_full_text(result_item):
    st.session_state.selected_item = result_item
    st.session_state.search_query = ""
    st.rerun() # [V12] 즉시 새로고침

def go_to_main():
    st.session_state.selected_item = None
    st.session_state.search_query = ""
    st.rerun() # [V12] 즉시 새로고침

# --- 4. 메인 화면 (3가지 모드) ---

# [V12] UI 레이아웃 1: 검색창 (항상 최상단)
query = st.text_input(
    "🔍 검색어를 입력하세요 (예: '용접', '추락', '고소 작업대')", 
    key="search_query"
)

if query:
    # --- 모드 1: 검색 결과 표시 ---
    st.session_state.selected_item = None 
    final_indices = []
    
    # 1. 유의어 검색
    norm_query = normalize_text(query)
    if norm_query in synonyms:
        synonym_ids = synonyms[norm_query]
        synonym_df_indices = df[df['id'].isin(synonym_ids)].index
        final_indices.extend(synonym_df_indices)
    
    # 2. 키워드 검색
    normalized_keywords = [normalize_text(k) for k in query.split() if k]
    keyword_results = df.copy()
    if normalized_keywords:
        for kw in normalized_keywords:
            keyword_results = keyword_results[keyword_results['search_normalized'].str.contains(kw, na=False)]
    
    keyword_indices = set(keyword_results.index)
    for idx in keyword_indices:
        if idx not in final_indices:
            final_indices.append(idx)
    
    # 3. AI 유사어 검색
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
    # --- 모드 2: 항목 본문(PDF) 표시 ---
    item = st.session_state.selected_item
    
    st.button("← 목차로 돌아가기", on_click=go_to_main)
    st.markdown(f"## {item['full_title']}")
    
    page_start = item['page_start']
    page_end = item.get('page_end', page_start)
    st.markdown(f"**페이지 번호:** {page_start} ~ {page_end}")
    st.markdown("---")
    
    for page_to_show in range(page_start, page_end + 1):
        st.subheader(f"📄 PDF 원본 보기 (Page {page_to_show})")
        img_bytes = render_pdf_page(PDF_FILE_NAME, page_to_show)
        if img_bytes:
            st.image(img_bytes, use_column_width=True)
        st.divider()

else:
    # --- 모드 3: 메인 화면 (목차 + 다운로드) ---
    st.subheader("📑 기준집 목차 (카테고리)")
    
    try:
        df['category'] = df['id'].apply(lambda x: x.split('-')[0])
        categories = sorted(df['category'].unique())
        
        # [V12 수정] 목차를 'expander'(펼치기/접기)로 표시
        for category in categories:
            with st.expander(f"📁 **{category}**"):
                category_items = df[df['category'] == category]
                for _, row in category_items.iterrows():
                    # 버튼 대신 st.page_link를 쓰면 더 깔끔할 수 있으나,
                    # 호환성을 위해 버튼 + 콜백 사용
                    st.button(
                        f"{row['full_title']}", 
                        key=f"toc_{row['id']}",
                        on_click=show_full_text,
                        args=(row,),
                        use_container_width=True # 버튼을 꽉 채움
                    )
    except Exception as e:
        st.error(f"목차를 불러오는 중 오류가 발생했습니다: {e}")

    st.divider()

    # [V12 수정] PDF 다운로드 버튼 (항상 최하단)
    try:
        with open(PDF_FILE_NAME, "rb") as f:
            st.download_button(
                label="기준집 PDF 전체 다운로드",
                data=f,
                file_name=PDF_FILE_NAME,
                mime="application/pdf",
                use_container_width=True # 버튼을 꽉 채움
            )
    except FileNotFoundError:
        st.error(f"'{PDF_FILE_NAME}' 파일을 찾을 수 없습니다.")