import streamlit as st
import os

# --- [모바일 배려] 상단 홈 버튼 ---
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# 1. 경로 설정 (최상위 manual_data 폴더 찾기)
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_folder_path = os.path.join(current_dir, "manual_data")

# 2. 스타일 설정
st.markdown("""
<style>
    /* 탭 글씨 크기 키우기 */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem; font-weight: bold;
    }
    /* 이미지 캡션 스타일 */
    .img-caption {
        font-size: 0.9rem; color: #555; margin-bottom: 20px; text-align: center; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# 3. 폴더 존재 여부 확인
if not os.path.exists(base_folder_path):
    st.error(f"❌ '{base_folder_path}' 폴더가 없습니다.")
    st.info("Home.py가 있는 위치에 'manual_data' 폴더를 만들어주세요.")
    st.stop()

# 4. 1단계: 사이드바 메뉴 (대분류)
categories = sorted([d for d in os.listdir(base_folder_path) if os.path.isdir(os.path.join(base_folder_path, d))])

if not categories:
    st.warning("📂 'manual_data' 폴더 안에 대분류 폴더(예: 01_장비작업)가 없습니다.")
    st.stop()

st.sidebar.title("📂 작업 그룹")
selected_category = st.sidebar.radio("확인할 작업을 선택하세요:", categories)

# 5. 메인 화면 구성
st.title(f"📖 {selected_category}")

category_path = os.path.join(base_folder_path, selected_category)
topics = sorted([d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))])

if topics:
    # 6. 2단계: 상단 탭 (중분류)
    tabs = st.tabs(topics)
    
    for i, topic in enumerate(topics):
        with tabs[i]:
            topic_path = os.path.join(category_path, topic)
            sub_folders = sorted([d for d in os.listdir(topic_path) if os.path.isdir(os.path.join(topic_path, d))])
            
            # 7. 3단계: 확장형 박스 (소분류)
            if sub_folders:
                for sub in sub_folders:
                    sub_path = os.path.join(topic_path, sub)
                    images = sorted([f for f in os.listdir(sub_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                    
                    # 클릭하면 열리는 박스 (기본값: 닫힘)
                    with st.expander(f"📌 {sub} (눌러서 내용 보기)", expanded=False):
                        if images:
                            for img_file in images:
                                # 파일명 깔끔하게 처리
                                caption = os.path.splitext(img_file)[0]
                                if "_" in caption: 
                                    display_caption = caption.split("_", 1)[1]
                                else:
                                    display_caption = caption
                                    
                                st.image(os.path.join(sub_path, img_file), use_container_width=True)
                                st.markdown(f"<div class='img-caption'>{display_caption}</div>", unsafe_allow_html=True)
                        else:
                            st.info("이미지가 없습니다.")
            else:
                # 하위 폴더 없이 이미지만 있는 경우 (예외 처리)
                images_in_root = sorted([f for f in os.listdir(topic_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                if images_in_root:
                     for img_file in images_in_root:
                        st.image(os.path.join(topic_path, img_file), use_container_width=True)
                else:
                    st.warning("하위 폴더(소분류)가 없습니다. 폴더 구조를 확인해주세요.")
else:

    st.info("탭(중분류) 폴더가 없습니다.")
