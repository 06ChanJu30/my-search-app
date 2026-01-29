import streamlit as st
import os

# 1. 페이지 설정
st.set_page_config(
    page_title="현장 안전 통합 시스템",
    page_icon="👷",
    layout="wide"
)

# 2. 로고 찾기 로직 (자동 감지)
current_dir = os.path.dirname(os.path.abspath(__file__)) # Home.py가 있는 위치
possible_logos = ["logo.png", "logo.jpg", "logo.jpeg", "Logo.png", "Logo.jpg"]
found_logo = None

for img_name in possible_logos:
    img_path = os.path.join(current_dir, img_name)
    if os.path.exists(img_path):
        found_logo = img_path
        break

# 3. 화면 구성
col_head1, col_head2 = st.columns([1, 6]) # 로고 영역 비율 조정

with col_head1:
    if found_logo:
        st.image(found_logo, width=150) # 로고 크기 조절
    else:
        # 로고를 못 찾았을 때 디버깅용 메시지 (나중에 지우셔도 됩니다)
        st.write("❌ 로고 없음")
        
with col_head2:
    st.title("현장 안전 통합 시스템")
    st.subheader("Safety Management System")

# (디버깅) 만약 로고가 안 나오면 아래 주석을 풀고 화면에 파일 목록을 확인해보세요
# st.warning(f"현재 폴더의 파일들: {os.listdir(current_dir)}")

st.markdown("---")

# 4. 메인 네비게이션 버튼
st.info("👇 원하시는 작업을 선택해주세요.")

col1, col2 = st.columns(2)

with col1:
    st.header("🔍 안전 기준 검색")
    st.write("산업안전보건 기준 및 사내 규정 검색")
    st.page_link("pages/01_안전기준검색.py", label="기준집 검색 바로가기", icon="🔍", use_container_width=True)

with col2:
    st.header("📖 작업 절차서 열람")
    st.write("표준 작업안 및 장비 사용 매뉴얼 확인")
    st.page_link("pages/02_작업절차서.py", label="작업 절차서 바로가기", icon="📖", use_container_width=True)
