import streamlit as st
import os
import fitz  # PyMuPDF

# --- 상단 홈 버튼 ---
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# --- 1. 경로 및 파일 설정 ---
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_FILE_NAME = "ground_rule.pdf"
pdf_path = os.path.join(current_dir, PDF_FILE_NAME)

st.title("📚 Safety Ground Rule")
st.info("안전 그라운드 룰을 항목별로 확인하실 수 있습니다.")

# --- 2. 기능 함수: PDF 페이지 렌더링 ---
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

# --- 3. 스마트하게 목차 나누기 ---
@st.cache_data
def parse_ground_rules(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    
    doc = fitz.open(pdf_path)
    rules = []
    current_title = "표지 및 개요"
    current_pages = []

    for i in range(len(doc)):
        page = doc.load_page(i)
        text = page.get_text("text")
        
        found_title = None
        for line in text.split('\n'):
            clean_line = line.lower().replace(" ", "").replace("*", "")
            if "safetygroundrule" in clean_line:
                found_title = line.strip()
                break
        
        if found_title:
            if found_title == current_title:
                current_pages.append(i)
            else:
                if current_pages:
                    rules.append({"title": current_title, "pages": current_pages})
                current_title = found_title
                current_pages = [i]
        else:
            current_pages.append(i)
            
    if current_pages:
        rules.append({"title": current_title, "pages": current_pages})
        
    doc.close()
    return rules

# --- 4. 메인 화면 출력 ---
if not os.path.exists(pdf_path):
    st.error(f"❌ '{PDF_FILE_NAME}' 파일을 찾을 수 없습니다.")
    st.warning("서버 최상위 폴더에 파일이 제대로 올라갔는지, 파일 이름이 정확한지 확인해주세요.")
else:
    with st.spinner("문서를 분석하여 목차를 정리하고 있습니다... (최초 1회만 소요)"):
        parsed_rules = parse_ground_rules(pdf_path)
        
    if parsed_rules:
        # 추출한 목차대로 아코디언 만들기
        for rule in parsed_rules:
            if not rule["pages"]:
                continue
                
            # 박스 제목 생성
            with st.expander(f"📌 {rule['title']} (총 {len(rule['pages'])}장)", expanded=False):
                
                # 💡 [추가된 부분] '표지 및 개요' 항목일 경우 맨 위에 다운로드 버튼 표시
                if rule['title'] == "표지 및 개요":
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="📥 전체 PDF 파일 다운로드",
                            data=pdf_file,
                            file_name="Safety_Ground_Rule.pdf", # 다운로드될 때의 파일 이름
                            mime="application/pdf",
                            type="primary", # 버튼을 눈에 띄는 파란색으로 강조
                            use_container_width=True # 화면 가로 길이에 맞게 꽉 차게
                        )
                    st.divider() # 버튼과 이미지 사이에 얇은 선 긋기

                # 이미지 렌더링
                for page_index in rule["pages"]:
                    img_bytes = render_pdf_page(pdf_path, page_index)
                    if img_bytes:
                        st.image(img_bytes, use_container_width=True)
                        st.caption(f"- {page_index + 1} 페이지 -")
                        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.warning("문서 내용을 분석할 수 없습니다. (PDF가 스캔된 이미지 파일일 수 있습니다)")

# --- 5. 하단 문의처 (사이드바 공통) ---
with st.sidebar:
    st.caption("**안전팀 (백찬주 대리)**")
    st.code("010-2528-5706", language="python")
    st.markdown("📧 [이메일 보내기](mailto:king990630@gmail.com)")

