import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import datetime
import csv

# ---------------------------------------------------------
# 1. 페이지 설정 및 모바일 UI 최적화 (Task 6)
# ---------------------------------------------------------
# 모바일 환경을 고려하여 사이드바 최소화 및 레이아웃 최적화
st.set_page_config(page_title="작업지침 OPS 검색기", layout="centered", initial_sidebar_state="collapsed")

# 모바일 화면에서는 컬럼 배율이 자동으로 세로 정렬됨
col1, col2 = st.columns([1.5, 8.5], vertical_alignment="center")
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=80) # 모바일 대응 크기 축소
    else:
        st.markdown("<h1>💡</h1>", unsafe_allow_html=True)
with col2:
    st.markdown("### 🚧 안전보건 작업지침 OPS")

st.caption("개정된 삼성물산 7대 분류(공통, 장비, 보건, 건축, 토목, ES, 하이테크) 적용 완료")

# ---------------------------------------------------------
# 2. 리소스 및 디렉토리 설정
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")
if not os.path.exists(JSON_FILE_PATH):
    JSON_FILE_PATH = os.path.join(current_dir, "standards_data.json")
    
PDF_FILE_PATH = os.path.join(current_dir, "안전보건 작업지침 OPS.pdf") 
VECTOR_INDEX_PATH = os.path.join(current_dir, "vector_db.index") # FAISS 인덱스 경로
LOG_FILE_PATH = os.path.join(current_dir, "search_logs.csv") # 검색 로그 파일

# ---------------------------------------------------------
# 3. 데이터 로딩 & 카테고리 설정
# ---------------------------------------------------------
CATEGORY_KEYWORDS = {
    '1. 공통': ['보호구', '공도구', '철근', '거푸집', '동바리', '화기작업', '콘크리트', '비계', '추락', '낙하', '전기', '하역', '운반', '화재', '가설', '안전벨트', '생명줄', '난간'],
    '2. 장비': ['크레인', '리프트', '곤돌라', '고소작업', '지게차', '굴착기', '토공장비', '항타', '천공기', '타설장비', '해상장비', '특수장비', '줄걸이', '사다리차', '압축기', '압력용기', '모듈화장비', '로봇', '양중'],
    '3. 보건': ['밀폐공간', '방사선', '유해위험물질', '질식', 'MSDS', '보건'],
    '4. 건축': ['철골', '해체', '철거', '습식', '외장', '내장', 'PC', '도장', '방수', '조경', '엘리베이터', '에스컬레이터', '건축'],
    '5. 토목': ['토공', '벌목', '발파', '항타작업', '터널', '교량', '댐', '흙막이', '포장', '항만', '토목'],
    '6. ES': ['시운전', 'LOTO', '원자로', '보일러', '철탑', 'LNG', '태양광'],
    '7. 하이테크': ['배관', '모듈화시공', '천장', '하이테크']
}

def assign_major_category(title, category, doc_id):
    text = str(title) + str(category) + str(doc_id)
    if 'IZ12B-1' in text: return '1. 공통'
    elif 'IZ12B-2' in text: return '2. 장비'
    elif 'IZ12B-3' in text: return '3. 보건'
    elif 'IZ12B-4' in text: return '4. 건축'
    elif 'IZ12B-5' in text: return '5. 토목'
    elif 'IZ12B-6' in text: return '6. ES'
    elif 'IZ12B-7' in text: return '7. 하이테크'
    
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return cat
    return '1. 공통'

@st.cache_data(show_spinner="데이터베이스를 읽어오는 중입니다...")
def load_ops_data():
    if not os.path.exists(JSON_FILE_PATH):
        return pd.DataFrame()
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            df = pd.DataFrame(json.load(f))
        
        if not df.empty:
            df = df[~df['title'].str.contains('개정이력|목차', case=False, na=False)]
            if 'search_normalized' not in df.columns: df['search_normalized'] = ""
            if 'title' not in df.columns: df['title'] = "제목없음"
            
            df['major_category'] = df.apply(lambda row: assign_major_category(row.get('title', ''), row.get('category', ''), row.get('id', '')), axis=1)
            df['clean_title'] = df['title'].str.replace(r'[^가-힣a-zA-Z0-9]', '', regex=True)
            df = df.drop_duplicates(subset=['clean_title'], keep='first')
            # id 컬럼이 없다면 생성 (Vector DB 매핑용)
            if 'id' not in df.columns:
                df['id'] = df.index.astype(str)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_resource(show_spinner="PDF 매뉴얼 데이터를 준비 중입니다...")
def load_pdf_bytes():
    if os.path.exists(PDF_FILE_PATH):
        with open(PDF_FILE_PATH, "rb") as f:
            return f.read()
    return None

# ---------------------------------------------------------
# [Task 4] AI 의미론적 검색 (FAISS + SentenceTransformers) 로드
# ---------------------------------------------------------
@st.cache_resource(show_spinner="AI 추천 엔진을 메모리에 올리는 중입니다...")
def load_ai_models():
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        
        # 한국어 임베딩 모델 로딩
        model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS")
        index = faiss.read_index(VECTOR_INDEX_PATH) if os.path.exists(VECTOR_INDEX_PATH) else None
        return model, index
    except ImportError:
        # 라이브러리가 없는 경우 우회 (일반 검색만 동작)
        return None, None
    except Exception as e:
        st.warning(f"AI 모델 연동 오류 (키워드 검색은 정상 작동합니다): {e}")
        return None, None

df = load_ops_data()
pdf_bytes = load_pdf_bytes()
ai_model, faiss_index = load_ai_models()

if df.empty:
    st.error("데이터베이스 파일이 없습니다. (ops_database.json 필요)")
    st.stop()

# ---------------------------------------------------------
# [Task 5] 검색 로그 자동 수집 시스템 구축
# ---------------------------------------------------------
def log_search(query, result_count):
    """사용자 검색어와 결과 건수를 백그라운드에서 CSV로 저장합니다."""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_exists = os.path.exists(LOG_FILE_PATH)
        with open(LOG_FILE_PATH, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Search Query", "Result Count"])
            writer.writerow([now, query, result_count])
    except Exception as e:
        pass # 로그 저장 실패로 인해 메인 기능이 멈추지 않도록 처리

@st.cache_data(show_spinner=False)
def convert_df_to_csv(result_dataframe):
    export_df = result_dataframe.drop(columns=['search_normalized', 'clean_title', 'match_score'], errors='ignore')
    return export_df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 4. 화면 렌더링 로직 (PDF 하이라이트 일회성 처리 적용)
# ---------------------------------------------------------
def display_manual_content(row, keywords=None):
    if pdf_bytes is None:
        st.info(f"{row.get('answer', '내용없음')}")
        return

    local_pdf = fitz.open("pdf", pdf_bytes)
    content_displayed = False
    
    try:
        if 'page_start' in row and pd.notna(row['page_start']) and row['page_start'] != "":
            try:
                p_start = int(row['page_start'])
                p_end = int(row.get('page_end', p_start))

                for p in range(p_start, p_end + 1):
                    page_idx = p - 1
                    if 0 <= page_idx < len(local_pdf):
                        page = local_pdf[page_idx]
                        
                        if keywords:
                            for kw in keywords:
                                text_instances = page.search_for(kw)
                                for inst in text_instances:
                                    page.add_highlight_annot(inst).update()
                        
                        pix = page.get_pixmap(dpi=120) # 모바일 최적화를 위해 dpi 120으로 소폭 하향 조정
                        st.image(pix.tobytes("png"), caption=f"원본 매뉴얼 (p.{p})", use_container_width=True)
                        content_displayed = True
            except ValueError:
                pass

        if not content_displayed:
            ref = row.get('reference', '')
            match = re.search(r'\(p\.(\d+)\)', ref)
            if match:
                page_idx = int(match.group(1)) - 1
                if 0 <= page_idx < len(local_pdf):
                    page = local_pdf[page_idx]
                    
                    if keywords:
                        for kw in keywords:
                            for inst in page.search_for(kw):
                                page.add_highlight_annot(inst).update()
                                
                    pix = page.get_pixmap(dpi=120)
                    st.image(pix.tobytes("png"), caption=f"원본 매뉴얼 (p.{page_idx + 1})", use_container_width=True)
            else:
                st.info(f"{row.get('answer', '내용없음')}")
    finally:
        local_pdf.close()

# ---------------------------------------------------------
# 5. 메인 UI 및 하이브리드 검색 로직
# ---------------------------------------------------------
# 검색창 디자인 
query = st.text_input("🔍 안전 지침 검색", placeholder="타워크레인, 밀폐공간, 추락 방지 등 입력")

if query:
    keywords = query.strip().split()
    mask = pd.Series([True] * len(df), index=df.index)
    
    # --- [Step 1] 정확한 키워드 매칭 검색 ---
    for kw in keywords:
        kw_lower = kw.lower()
        kw_mask = df['title'].str.lower().str.contains(kw_lower, regex=False, na=False) | \
                  df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False)
        mask = mask & kw_mask
        
    result_df = df[mask]
    
    # [Task 5] 검색 로그 기록
    log_search(query, len(result_df))
    
    if len(result_df) > 0:
        st.success(f"총 {len(result_df)}건의 지침을 찾았습니다.")
        
        # 모바일에서도 잘 보이도록 열 배치 간소화
        csv_data = convert_df_to_csv(result_df)
        st.download_button(
            label="📥 검색 결과 다운로드 (Excel/CSV)",
            data=csv_data,
            file_name="ops_search_results.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.divider()
        
        for _, row in result_df.iterrows():
            with st.expander(f"📘 [{row['major_category']}] {row.get('title', '제목없음')}"):
                display_manual_content(row, keywords=keywords) 
    else:
        st.warning("정확히 일치하는 단어가 포함된 지침이 없습니다.")
    
    # --- [Step 2] AI 의미론적 검색 (Task 4) ---
    # 결과가 3개 이하일 때만 AI 기반 추천을 실행하여 화면 복잡도 최소화
    if len(result_df) <= 3:
        st.markdown("### 💡 AI 연관 지침 추천")
        
        if ai_model and faiss_index:
            # 벡터 DB 기반 의미론적 검색 수행
            try:
                import numpy as np
                query_vector = ai_model.encode([query]).astype('float32')
                k = 5 # 추천 5개
                distances, indices = faiss_index.search(query_vector, k)
                
                # 매칭된 인덱스 번호를 바탕으로 df 매핑 (벡터 DB 생성 시의 인덱스와 동일해야 함)
                matched_indices = [idx for idx in indices[0] if idx != -1]
                
                if matched_indices:
                    # 결과에 이미 포함된 문서 제외
                    recommend_df = df.iloc[matched_indices]
                    recommend_df = recommend_df[~recommend_df.index.isin(result_df.index)]
                    
                    for _, row in recommend_df.head(3).iterrows():
                        with st.expander(f"✨(AI 추천) [{row['major_category']}] {row.get('title', '제목없음')}"):
                            display_manual_content(row, keywords=keywords)
            except Exception as e:
                st.error("AI 검색 처리 중 문제가 발생했습니다.")
                
        else:
            # AI 모델이나 인덱스가 없을 경우 기존 유사도 검색 유지 (Fallback)
            df['match_score'] = 0 
            for kw in keywords:
                kw_lower = kw.lower()
                df.loc[df['search_normalized'].str.lower().str.contains(kw_lower, na=False), 'match_score'] += 1
                df.loc[df['title'].str.lower().str.contains(kw_lower, na=False), 'match_score'] += 2
            
            recommend_df = df[~df.index.isin(result_df.index)]
            recommend_df = recommend_df[recommend_df['match_score'] >= 1].sort_values(by='match_score', ascending=False).head(3)
            
            for _, row in recommend_df.iterrows():
                with st.expander(f"🔍(관련 문서) [{row['major_category']}] {row.get('title', '제목없음')}"):
                    display_manual_content(row, keywords=keywords)

else:
    # 검색어가 없을 경우 모바일 친화적인 목차 뷰
    st.markdown("### 📑 분야별 작업지침 목차")
    categories = sorted(list(df['major_category'].unique()))
    selected_toc = st.selectbox("조회할 카테고리를 선택하세요", ["(카테고리 선택)"] + categories)
    
    if selected_toc != "(카테고리 선택)":
        cat_df = df[df['major_category'] == selected_toc]
        for _, row in cat_df.iterrows():
            with st.expander(f"📘 {row.get('title', '제목없음')}"):
                display_manual_content(row) 

st.divider()
st.caption("📄 문의: 안전팀 백찬주 대리 (010-2528-5706")
