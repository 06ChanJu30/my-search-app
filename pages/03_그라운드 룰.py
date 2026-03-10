import streamlit as st
import os
import fitz  # PyMuPDF

# --- 상단 홈 버튼 ---
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# --- 1. 경로 및 파일 설정 ---
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_FILE_NAME = "ground_rule.pdf"  # 👈 올리신 PDF 파일 이름과 똑같아야 합니다!
pdf_path = os.path.join(current_dir, PDF_FILE_NAME)

st.title("📚 Safety Ground Rule")
st.info("안전 그라운드 룰을 항목별로 확인하실 수 있습니다.")

# --- 2. 기능 함수: PDF 페이지 이미지로 바꾸기 ---
@st.cache_data
def render_pdf_page(pdf_path, page_num, dpi=150):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=dpi)
        doc.close()
        return pix.tobytes("png")
    except Exception as e:
        return None

# --- 3. 기능 함수: PDF 텍스트를 읽고 자동으로 목차 나누기 ---
@st.cache_data
def parse_ground_rules(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    
    doc = fitz.open(pdf_path)
    rules = []
    current_title = "표지 및 개요" # 맨 처음 ***가 나오기 전까지의 페이지들
    current_pages = []

    for i in range(len(doc)):
        page = doc.load_page(i)
        text = page.get_text("text")
        
        found_title = None
        # 페이지의 모든 줄을 검사해서 규칙 찾기
        for line in text.split('\n'):
            # 대소문자나 띄어쓰기가 달라도 찾을 수 있게 변환해서 검사
            clean_line = line.lower().replace(" ", "")
            if "***safetygroundrule" in clean_line:
                # 실제 화면에 보여줄 제목 (예: "*** safety ground rule - 고소작업")
                found_title = line.strip() 
                break
        
        if found_title:
            # 새로운 규칙이 나타나면, 이전까지 모은 페이지들을 묶어서 저장
            if current_pages:
                rules.append({"title": current_title, "pages": current_pages})
            current_title = found_title
            current_pages = [i] # 새 카테고리 시작
        else:
            # 규칙 문구가 없으면 계속 현재 카테고리에 페이지를 추가
            current_pages.append(i)
            
    # 마지막으로 남은 페이지 묶음 저장
    if current_pages:
        rules.append({"title": current_title, "pages": current_pages})
        
    doc.close()
    return rules

# --- 4. 메인 화면 출력 로직 ---
if not os.path.exists(pdf_path):
    st.error(f"❌ '{PDF_FILE_NAME}' 파일을 찾을 수 없습니다.")
    st.warning(f"서버 최상위 폴더에 '{PDF_FILE_NAME}' 파일이 제대로 올라갔는지 확인해주세요!")
else:
    with st.spinner("문서를 분석하여 목차를 정리하고 있습니다... (최초 1회만 소요)"):
        parsed_rules = parse_ground_rules(pdf_path)
        
    if parsed_rules:
        # 추출한 목차대로 아코디언(열고 닫는 박스) 만들기
        for rule in parsed_rules:
            if not rule["pages"]:
                continue
                
            # 박스 제목 생성
            with st.expander(f"📌 {rule['title']} (총 {len(rule['pages'])}장)", expanded=False):
                for page_index in rule["pages"]:
                    img_bytes = render_pdf_page(pdf_path, page_index)
                    if img_bytes:
                        st.image(img_bytes, use_container_width=True)
                        st.caption(f"- {page_index + 1} 페이지 -")
                        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.warning("문서 내용을 분석할 수 없습니다.")

# --- 5. 하단 문의처 (사이드바 공통) ---
with st.sidebar:
    st.caption("**안전팀 (백찬주 대리)**")
    st.code("010-2528-5706", language="python")
    st.markdown("📧 [이메일 보내기](mailto:king990630@gmail.com)")