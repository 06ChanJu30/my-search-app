import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF

# ---------------------------------------------------------
# 1. 페이지 설정 및 로고
# ---------------------------------------------------------
st.set_page_config(page_title="작업지침 OPS 검색기", layout="centered")

col1, col2 = st.columns([1.5, 8.5])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    else:
        st.markdown("<h1>💡</h1>", unsafe_allow_html=True)
with col2:
    st.title("안전보건 작업지침 OPS")

st.caption("개정된 삼성물산 7대 분류(공통, 장비, 보건, 건축, 토목, ES, 하이테크) 적용 완료")

if st.button("🔄 최신 데이터 불러오기"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")
if not os.path.exists(JSON_FILE_PATH):
    JSON_FILE_PATH = os.path.join(current_dir, "standards_data.json")
    
PDF_FILE_PATH = os.path.join(current_dir, "안전보건 작업지침 OPS.pdf") 

# ---------------------------------------------------------
# 2. 카테고리 매핑 설정 (Task 2: 하드코딩 분리 및 모듈화)
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
    """제목, 카테고리, ID를 조합하여 7대 분류를 할당합니다."""
    text = str(title) + str(category) + str(doc_id)
    
    # 1차 판별: 문서 코드 기준
    if 'IZ12B-1' in text: return '1. 공통'
    elif 'IZ12B-2' in text: return '2. 장비'
    elif 'IZ12B-3' in text: return '3. 보건'
    elif 'IZ12B-4' in text: return '4. 건축'
    elif 'IZ12B-5' in text: return '5. 토목'
    elif 'IZ12B-6' in text: return '6. ES'
    elif 'IZ12B-7' in text: return '7. 하이테크'
    
    # 2차 판별: 키워드 매핑
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return cat
            
    return '1. 공통' # 기본값

# ---------------------------------------------------------
# 3. 데이터 및 리소스 캐싱 로드
# ---------------------------------------------------------
@st.cache_data(show_spinner="데이터베이스(JSON)를 메모리에 로딩 중입니다...")
def load_ops_data():
    if not os.path.exists(JSON_FILE_PATH):
        return pd.DataFrame()
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df[~df['title'].str.contains('개정이력|목차', case=False, na=False)]
            
            if 'search_normalized' not in df.columns:
                df['search_normalized'] = ""
            if 'title' not in df.columns:
                df['title'] = "제목없음"
                
            # 모듈화된 함수 적용
            df['major_category'] = df.apply(lambda row: assign_major_category(row.get('title', ''), row.get('category', ''), row.get('id', '')), axis=1)
            
            df['clean_title'] = df['title'].str.replace(r'[^가-힣a-zA-Z0-9]', '', regex=True)
            df = df.drop_duplicates(subset=['clean_title'], keep='first')
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

# [Task 1 개선] PDF 객체 대신 '바이트(Bytes) 데이터'를 캐싱하여 스레드 안전성 확보
@st.cache_resource(show_spinner="원본 PDF 매뉴얼 데이터를 로딩 중입니다...")
def load_pdf_bytes():
    if os.path.exists(PDF_FILE_PATH):
        with open(PDF_FILE_PATH, "rb") as f:
            return f.read()
    return None

df = load_ops_data()
pdf_bytes = load_pdf_bytes()

if df.empty:
    st.error("데이터베이스 파일이 없습니다. 깃허브에 JSON 데이터 파일을 업로드해주세요.")
    st.stop()

# [Task 3 개선] 다운로드 데이터 연산 결과를 캐싱하여 반복 연산 방지
@st.cache_data(show_spinner=False)
def convert_df_to_csv(result_dataframe):
    export_df = result_dataframe.drop(columns=['search_normalized', 'clean_title', 'match_score'], errors='ignore')
    return export_df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 4. 화면 렌더링 로직 (Task 1: PDF 인스턴스 일회성 로드)
# ---------------------------------------------------------
def display_manual_content(row, keywords=None):
    if pdf_bytes is None:
        st.warning("원본 PDF 파일이 연결되어 있지 않습니다.")
        st.info(f"{row.get('answer', '내용없음')}")
        return

    # [Task 1 개선] 캐싱된 바이트 데이터에서 매 렌더링마다 독립된 PDF 객체 생성 (충돌 원천 차단)
    local_pdf = fitz.open("pdf", pdf_bytes)
    content_displayed = False
    
    try:
        # 다중 페이지 출력 로직
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
                                    annot = page.add_highlight_annot(inst)
                                    annot.update()
                        
                        pix = page.get_pixmap(dpi=150)
                        img_data = pix.tobytes("png")
                        
                        st.image(img_data, caption=f"원본 매뉴얼 (페이지 {p})", use_container_width=True)
                        if p != p_end: 
                            st.markdown("<br>", unsafe_allow_html=True)
                        content_displayed = True
                    else:
                        st.error(f"해당 페이지({p})를 PDF에서 찾을 수 없습니다.")
            except ValueError:
                pass

        # 구버전 데이터 호환 로직
        if not content_displayed:
            ref = row.get('reference', '')
            match = re.search(r'\(p\.(\d+)\)', ref)
            if match:
                page_idx = int(match.group(1)) - 1
                if 0 <= page_idx < len(local_pdf):
                    page = local_pdf[page_idx]
                    
                    if keywords:
                        for kw in keywords:
                            text_instances = page.search_for(kw)
                            for inst in text_instances:
                                annot = page.add_highlight_annot(inst)
                                annot.update()
                                
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    
                    st.image(img_data, caption=f"원본 매뉴얼 (페이지 {page_idx + 1})", use_container_width=True)
                    content_displayed = True
                else:
                    st.error("해당 페이지를 PDF에서 찾을 수 없습니다.")
            else:
                st.info(f"{row.get('answer', '내용없음')}")
                
    finally:
        # 사용이 끝난 PDF 객체는 반드시 닫아 메모리 누수 방지
        local_pdf.close()

# ---------------------------------------------------------
# 5. 메인 검색 UI
# ---------------------------------------------------------
query = st.text_input("🔍 검색어를 입력하세요. (예: 타워크레인, 화기작업, IZ12B-104)")

if query:
    keywords = query.strip().split()
    mask = pd.Series([True] * len(df), index=df.index)
    
    try:
        # [1] 교집합(AND) 검색
        for kw in keywords:
            kw_lower = kw.lower()
            kw_mask = df['title'].str.lower().str.contains(kw_lower, regex=False, na=False) | \
                      df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False)
            mask = mask & kw_mask
            
        result_df = df[mask]
        
        if len(result_df) > 0:
            # [Task 3 개선] 다운로드 캐싱 연동
            col_res1, col_res2 = st.columns([7, 3])
            with col_res1:
                st.subheader(f"총 {len(result_df)}건의 검색 결과가 있습니다.")
            with col_res2:
                csv_data = convert_df_to_csv(result_df)
                st.download_button(
                    label="📥 검색 결과 엑셀(CSV) 다운로드",
                    data=csv_data,
                    file_name="ops_search_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.divider()
            
            for i, row in result_df.iterrows():
                with st.expander(f"📖 [{row['major_category']}] {row.get('title', '제목없음')}"):
                    display_manual_content(row, keywords=keywords) 
        else:
            st.warning("정확히 일치하는 지침이 없습니다.")
        
        # [2] 유사 검색(관련 검색어) 추천
        if len(result_df) <= 3:
            df['match_score'] = 0 
            for kw in keywords:
                kw_lower = kw.lower()
                content_match = df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False)
                df.loc[content_match, 'match_score'] += 1
                
                title_match = df['title'].str.lower().str.contains(kw_lower, regex=False, na=False)
                df.loc[title_match, 'match_score'] += 2
            
            recommend_df = df[~df.index.isin(result_df.index)]
            min_score_required = 1 if len(keywords) == 1 else 2
            recommend_df = recommend_df[recommend_df['match_score'] >= min_score_required]
            recommend_df = recommend_df.sort_values(by='match_score', ascending=False).head(5)
            
            if len(recommend_df) > 0:
                st.info(f"💡 혹시 이런 지침을 찾으시나요? (연관성이 높은 지침 추천)")
                for i, row in recommend_df.iterrows():
                    with st.expander(f"📖 [{row['major_category']}] {row.get('title', '제목없음')}"):
                        display_manual_content(row, keywords=keywords)

    except Exception as e:
        st.error(f"앗! 검색 중 문제가 발생했습니다: {e}")
        
else:
    # 목차 UI (검색어가 없을 때)
    st.subheader("📑 분야별 작업지침 목차")
    categories = sorted(list(df['major_category'].unique()))
    selected_toc = st.selectbox("📂 조회할 카테고리를 선택하세요", ["(목차를 선택해주세요)"] + categories)
    
    if selected_toc != "(목차를 선택해주세요)":
        cat_df = df[df['major_category'] == selected_toc]
        for _, row in cat_df.iterrows():
            with st.expander(f"📖 {row.get('title', '제목없음')}"):
                display_manual_content(row) 

# ---------------------------------------------------------
# 6. 하단 문의처
# ---------------------------------------------------------
st.divider()
st.caption("📄 문의: 안전팀 백찬주 대리 (010-2528-5706)")
