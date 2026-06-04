import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF

# 1. 페이지 기본 설정
st.set_page_config(page_title="작업지침 OPS 검색기", page_icon="💡", layout="centered")

st.title("💡 안전보건 작업지침 OPS 검색")
st.caption("검색 시 원본 매뉴얼(그림)이 바로 표시됩니다. (다중 키워드 띄어쓰기 검색 가능)")

current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")
PDF_FILE_PATH = os.path.join(current_dir, "안전보건 작업지침 OPS.pdf") # 원본 PDF 파일

# 2. 데이터 불러오기 및 🌟가짜 데이터 완벽 제거🌟
@st.cache_data
def load_ops_data():
    if not os.path.exists(JSON_FILE_PATH):
        return pd.DataFrame()
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            # 💡 핵심 수정 1: 문서번호(IZ12B-)가 나오기 전 쓸어담은 가짜 데이터('공통 지침')를 통째로 삭제!
            df = df[df['category'] != '공통 지침']
            
            # (혹시 몰라 남겨두는 2차 방어선)
            df = df[~df['title'].str.contains('개정이력|목차', case=False, na=False)]
            
            # 💡 핵심 수정 2: 띄어쓰기, 특수문자 무시한 초강력 중복 제거
            df['clean_title'] = df['title'].str.replace(r'[^가-힣a-zA-Z0-9]', '', regex=True)
            df = df.drop_duplicates(subset=['clean_title'], keep='first')
            
        return df
    except Exception as e:
        return pd.DataFrame()

df = load_ops_data()

# 3. PDF 파일 불러오기
@st.cache_resource
def load_pdf():
    if os.path.exists(PDF_FILE_PATH):
        return fitz.open(PDF_FILE_PATH)
    return None

pdf_doc = load_pdf()

if df.empty:
    st.error("데이터베이스(ops_database.json)가 없습니다.")
    st.stop()

# 4. 검색창
query = st.text_input("🔍 검색어를 입력하세요. (예: 타워크레인 신호수, 화기작업)")

# 5. 엄격한 검색(AND) 및 그림 표시 로직
if query:
    keywords = query.strip().split()
    mask = pd.Series([True] * len(df), index=df.index)
    
    # 입력한 단어가 "모두" 포함된 지침만 정확하게 찾습니다.
    for kw in keywords:
        kw_mask = df['question'].str.contains(kw, case=False, na=False) | \
                  df['answer'].str.contains(kw, case=False, na=False)
        mask = mask & kw_mask
        
    result_df = df[mask]
    
    st.subheader(f"총 {len(result_df)}건의 작업지침이 검색되었습니다.")
    st.divider()
    
    if len(result_df) == 0:
        st.warning("정확히 일치하는 지침이 없습니다. 검색어를 줄이거나 단어를 바꿔서 다시 시도해보세요.")
    else:
        # 결과 출력 (아코디언 형태)
        for i, row in result_df.iterrows():
            with st.expander(f"📖 [{row.get('category', '분류없음')}] {row.get('title', '제목없음')}"):
                
                # 페이지 번호 추출 로직
                ref = row.get('reference', '')
                match = re.search(r'\(p\.(\d+)\)', ref)
                
                if pdf_doc is not None and match:
                    page_idx = int(match.group(1))
                    if 0 <= page_idx < len(pdf_doc):
                        page = pdf_doc[page_idx]
                        pix = page.get_pixmap(dpi=150) # 화질 설정
                        img_data = pix.tobytes("png")
                        
                        st.image(img_data, caption=f"원본 매뉴얼 (페이지 {page_idx + 1})", use_container_width=True)
                    else:
                        st.error("해당 페이지를 PDF에서 찾을 수 없습니다.")
                else:
                    st.warning("원본 PDF 파일이 없어 그림 대신 텍스트로 표시합니다.")
                    st.info(f"{row.get('answer', '내용없음')}")

# 6. 하단 문의처
st.divider()
col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("**담당자:** 안전팀 백찬주 대리")
    st.markdown("**전화:** 010-2528-5706")
