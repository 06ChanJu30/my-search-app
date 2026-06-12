import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF

# 1. 페이지 설정 및 로고
st.set_page_config(page_title="작업지침 OPS 검색기", layout="centered")

# 로고가 있으면 띄우고, 없으면 전구 아이콘을 띄우는 방어 로직
col1, col2 = st.columns([1.5, 8.5])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    else:
        st.markdown("<h1>💡</h1>", unsafe_allow_html=True)
with col2:
    st.title("안전보건 작업지침 OPS 검색")

st.caption("개정된 삼성물산 7대 분류(공통, 장비, 보건, 건축, 토목, ES, 하이테크) 적용 완료")

# 🌟 추가 기능: 캐시 초기화 버튼
if st.button("🔄 최신 데이터 불러오기 (검색 먹통 시 클릭!)"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")
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
            # 목차, 개정이력 등 불필요한 가짜 데이터 삭제
            df = df[~df['title'].str.contains('개정이력|목차', case=False, na=False)]
            
            # 🌟 [핵심] 개정된 7대 카테고리 강제 분류 로직 (문서번호 IZ12B-XXX 기준)
            def assign_major_category(row):
                text = str(row.get('title', '')) + str(row.get('category', ''))
                if 'IZ12B-1' in text: return '1. 공통'
                elif 'IZ12B-2' in text: return '2. 장비'
                elif 'IZ12B-3' in text: return '3. 보건'
                elif 'IZ12B-4' in text: return '4. 건축'
                elif 'IZ12B-5' in text: return '5. 토목'
                elif 'IZ12B-6' in text: return '6. ES'
                elif 'IZ12B-7' in text: return '7. 하이테크'
                else: return '기타 (공통/미분류)'
                
            df['major_category'] = df.apply(assign_major_category, axis=1)
            
            # 초강력 중복 제거
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
    st.error("데이터베이스(ops_database.json)가 없습니다. 파일을 깃허브에 업로드해주세요.")
    st.stop()

# 3. 개정된 카테고리 라디오 버튼 필터 생성
categories = ["전체"] + sorted(list(df['major_category'].unique()))
selected_cat = st.radio("📑 개정된 기준 카테고리 필터", categories, horizontal=True)

# 4. 검색창
query = st.text_input("🔍 검색어를 입력하세요. (예: 타워크레인, 화기작업, IZ12B-104)")

if query:
    if selected_cat != "전체":
        filtered_df = df[df['major_category'] == selected_cat]
    else:
        filtered_df = df

    keywords = query.strip().split()
    mask = pd.Series([True] * len(filtered_df), index=filtered_df.index)
    
    try:
        # 엄격한 다중 단어 교집합 검색
        for kw in keywords:
            kw_lower = kw.lower()
            kw_mask = filtered_df['question'].str.lower().str.contains(kw_lower, regex=False, na=False) | \
                      filtered_df['answer'].str.lower().str.contains(kw_lower, regex=False, na=False) | \
                      filtered_df['title'].str.lower().str.contains(kw_lower, regex=False, na=False)
            mask = mask & kw_mask
            
        result_df = filtered_df[mask]
        
        st.subheader(f"총 {len(result_df)}건의 작업지침이 검색되었습니다.")
        st.divider()
        
        if len(result_df) == 0:
            st.warning("정확히 일치하는 지침이 없습니다. 검색어를 줄이거나 단어를 바꿔서 다시 시도해보세요.")
        else:
            for i, row in result_df.iterrows():
                # 아코디언 제목에 개정된 7대 분류 카테고리가 예쁘게 달립니다!
                with st.expander(f"📖 [{row.get('major_category', '분류없음')}] {row.get('title', '제목없음')}"):
                    
                    ref = row.get('reference', '')
                    match = re.search(r'\(p\.(\d+)\)', ref)
                    
                    if pdf_doc is not None and match:
                        page_idx = int(match.group(1))
                        if 0 <= page_idx < len(pdf_doc):
                            page = pdf_doc[page_idx]
                            pix = page.get_pixmap(dpi=150)
                            img_data = pix.tobytes("png")
                            
                            st.image(img_data, caption=f"원본 매뉴얼 (페이지 {page_idx + 1})", use_container_width=True)
                        else:
                            st.error("해당 페이지를 PDF에서 찾을 수 없습니다.")
                    else:
                        st.warning("원본 PDF 파일이 없어 그림 대신 텍스트로 표시합니다.")
                        st.info(f"{row.get('answer', '내용없음')}")
                        
    except Exception as e:
        st.error("앗! 검색 중 문제가 발생했습니다. 검색어를 살짝 바꿔서 다시 시도해주세요.")

# 6. 하단 문의처
st.divider()
st.markdown("### 📞 도움이 필요하신가요?")
col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("**담당자:** 안전팀 백찬주 대리")
    st.markdown("**전화:** 010-2528-5706")
