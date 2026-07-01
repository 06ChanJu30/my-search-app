import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF

# 1. 페이지 설정 및 로고
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

@st.cache_data
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
                
            def assign_major_category(row):
                text = str(row.get('title', '')) + str(row.get('category', '')) + str(row.get('id', ''))
                if 'IZ12B-1' in text: return '1. 공통'
                elif 'IZ12B-2' in text: return '2. 장비'
                elif 'IZ12B-3' in text: return '3. 보건'
                elif 'IZ12B-4' in text: return '4. 건축'
                elif 'IZ12B-5' in text: return '5. 토목'
                elif 'IZ12B-6' in text: return '6. ES'
                elif 'IZ12B-7' in text: return '7. 하이테크'
                
                if any(k in text for k in ['보호구', '공도구', '철근', '거푸집', '동바리', '화기작업', '콘크리트', '비계', '추락', '낙하', '전기', '하역', '운반', '화재', '가설', '안전벨트', '생명줄', '난간']): return '1. 공통'
                elif any(k in text for k in ['크레인', '리프트', '곤돌라', '고소작업', '지게차', '굴착기', '토공장비', '항타', '천공기', '타설장비', '해상장비', '특수장비', '줄걸이', '사다리차', '압축기', '압력용기', '모듈화장비', '로봇', '양중']): return '2. 장비'
                elif any(k in text for k in ['밀폐공간', '방사선', '유해위험물질', '질식', 'MSDS', '보건']): return '3. 보건'
                elif any(k in text for k in ['철골', '해체', '철거', '습식', '외장', '내장', 'PC', '도장', '방수', '조경', '엘리베이터', '에스컬레이터', '건축']): return '4. 건축'
                elif any(k in text for k in ['토공', '벌목', '발파', '항타작업', '터널', '교량', '댐', '흙막이', '포장', '항만', '토목']): return '5. 토목'
                elif any(k in text for k in ['시운전', 'LOTO', '원자로', '보일러', '철탑', 'LNG', '태양광']): return '6. ES'
                elif any(k in text for k in ['배관', '모듈화시공', '천장', '하이테크']): return '7. 하이테크'
                else: return '1. 공통'
                
            df['major_category'] = df.apply(assign_major_category, axis=1)
            
            df['clean_title'] = df['title'].str.replace(r'[^가-힣a-zA-Z0-9]', '', regex=True)
            df = df.drop_duplicates(subset=['clean_title'], keep='first')
            
        return df
    except Exception as e:
        return pd.DataFrame()

df = load_ops_data()

@st.cache_resource
def load_pdf():
    if os.path.exists(PDF_FILE_PATH):
        return fitz.open(PDF_FILE_PATH)
    return None

pdf_doc = load_pdf()

if df.empty:
    st.error("데이터베이스 파일이 없습니다. 깃허브에 JSON 데이터 파일을 업로드해주세요.")
    st.stop()

# 🌟 그림 출력 및 하단 "닫기" 버튼 기능 추가
def display_manual_content(row):
    content_displayed = False
    
    if pdf_doc is None:
        st.warning("원본 PDF 파일이 연결되어 있지 않습니다.")
        st.info(f"{row.get('answer', '내용없음')}")
        content_displayed = True
    else:
        # 다중 페이지 출력 로직
        if 'page_start' in row and pd.notna(row['page_start']) and row['page_start'] != "":
            try:
                p_start = int(row['page_start'])
                p_end = int(row.get('page_end', p_start))

                for p in range(p_start, p_end + 1):
                    page_idx = p - 1
                    if 0 <= page_idx < len(pdf_doc):
                        page = pdf_doc[page_idx]
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
                if 0 <= page_idx < len(pdf_doc):
                    page = pdf_doc[page_idx]
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    st.image(img_data, caption=f"원본 매뉴얼 (페이지 {page_idx + 1})", use_container_width=True)
                    content_displayed = True
                else:
                    st.error("해당 페이지를 PDF에서 찾을 수 없습니다.")
            else:
                st.info(f"{row.get('answer', '내용없음')}")
                content_displayed = True
                
    # 🌟 [추가된 부분] 모든 페이지가 출력된 후 맨 아래에 '닫기' 버튼 생성
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # 고유한 버튼을 만들기 위해 문서 번호(id) 사용
        doc_id = row.get('id', row.get('title', 'unknown'))
        # 버튼을 누르면 st.rerun()이 실행되어 앱이 새로고침되며 자연스럽게 아코디언이 닫힘
        if st.button("접기 (닫기) ⬆️", key=f"close_{doc_id}", use_container_width=True):
            st.rerun()

# 3. 검색창
query = st.text_input("🔍 검색어를 입력하세요. (예: 타워크레인, 화기작업, IZ12B-104)")

# 4. 화면 분기
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
            st.subheader(f"총 {len(result_df)}건의 검색 결과가 있습니다.")
            st.divider()
            for i, row in result_df.iterrows():
                with st.expander(f"📖 [{row['major_category']}] {row.get('title', '제목없음')}"):
                    display_manual_content(row)
        else:
            st.warning("정확히 일치하는 지침이 없습니다.")
        
        # [2] 유사 검색(관련 검색어) 로직
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
                        display_manual_content(row)

    except Exception as e:
        st.error(f"앗! 검색 중 문제가 발생했습니다: {e}")
        
else:
    # 깔끔한 드롭다운(선택 상자) 목차 UI
    st.subheader("📑 분야별 작업지침 목차")
    categories = sorted(list(df['major_category'].unique()))
    selected_toc = st.selectbox("📂 조회할 카테고리를 선택하세요", ["(목차를 선택해주세요)"] + categories)
    
    if selected_toc != "(목차를 선택해주세요)":
        cat_df = df[df['major_category'] == selected_toc]
        for _, row in cat_df.iterrows():
            with st.expander(f"📖 {row.get('title', '제목없음')}"):
                display_manual_content(row)

# 6. 하단 문의처
st.divider()
st.caption("📄 문의: 안전팀 백찬주 대리 (010-2528-5706)")
