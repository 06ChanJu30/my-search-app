import streamlit as st
import os
from PIL import Image # 👈 이미지 회전을 위해 추가된 도구

# --- 상단 홈 버튼 ---
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# 1. 경로 설정
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_folder_path = os.path.join(current_dir, "manual_data")

# 2. 스타일 설정
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem; font-weight: bold;
    }
    .img-caption {
        font-size: 0.9rem; color: #555; margin-bottom: 20px; text-align: center; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# 3. 폴더 존재 여부 확인
if not os.path.exists(base_folder_path):
    st.error(f"❌ '{base_folder_path}' 폴더가 없습니다.")
    st.stop()

# 4. 대분류 선택 (화면 중앙 드롭다운)
categories = sorted([d for d in os.listdir(base_folder_path) if os.path.isdir(os.path.join(base_folder_path, d))])

if not categories:
    st.warning("📂 'manual_data' 폴더 안에 대분류 폴더가 없습니다.")
    st.stop()

st.title("📖 작업 절차서 열람")
selected_category = st.selectbox("📂 확인할 작업 그룹(대분류)을 선택하세요:", categories)
st.markdown("---")

ALLOWED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')

# 5. 메인 화면 구성
category_path = os.path.join(base_folder_path, selected_category)
topics = sorted([d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))])

if topics:
    tabs = st.tabs(topics)
    
    for i, topic in enumerate(topics):
        with tabs[i]:
            topic_path = os.path.join(category_path, topic)
            sub_folders = sorted([d for d in os.listdir(topic_path) if os.path.isdir(os.path.join(topic_path, d))])
            
            if sub_folders:
                for sub in sub_folders:
                    sub_path = os.path.join(topic_path, sub)
                    images = sorted([f for f in os.listdir(sub_path) if f.lower().endswith(ALLOWED_EXTENSIONS)])
                    
                    with st.expander(f"📌 {sub} (눌러서 내용 보기)", expanded=False):
                        if images:
                            for img_file in images:
                                caption = os.path.splitext(img_file)[0]
                                display_caption = caption.split("_", 1)[1] if "_" in caption else caption
                                
                                # 📸 [이미지 회전 마법] 📸
                                img_path = os.path.join(sub_path, img_file)
                                try:
                                    img = Image.open(img_path)
                                    # 반시계 방향으로 90도 회전 (expand=True는 모서리가 안 잘리게 해줍니다)
                                    # 만약 시계 방향으로 돌리고 싶다면 90 대신 -90을 넣으세요!
                                    img_rotated = img.rotate(90, expand=True) 
                                    st.image(img_rotated, use_container_width=True)
                                except Exception as e:
                                    st.error(f"이미지를 불러오는 중 오류가 발생했습니다: {e}")
                                    
                                st.markdown(f"<div class='img-caption'>{display_caption}</div>", unsafe_allow_html=True)
                        else:
                            st.info("이미지가 없습니다.")
            else:
                images_in_root = sorted([f for f in os.listdir(topic_path) if f.lower().endswith(ALLOWED_EXTENSIONS)])
                if images_in_root:
                     for img_file in images_in_root:
                        img_path = os.path.join(topic_path, img_file)
                        try:
                            img = Image.open(img_path)
                            img_rotated = img.rotate(90, expand=True) # 여기도 똑같이 90도 회전
                            st.image(img_rotated, use_container_width=True)
                        except Exception as e:
                            st.error(f"오류: {e}")
                else:
                    st.warning("하위 폴더나 사진 파일이 없습니다.")
else:
    st.info("해당 작업 그룹에 등록된 내용이 없습니다.")

# --- 하단 문의처 (사이드바 공통) ---
with st.sidebar:
    st.markdown("---")
    st.markdown("안전팀 📞 010-2528-5706")
    st.caption("**👷 안전팀 (백찬주 대리)**")
    st.code("010-2528-5706", language="python")
    st.markdown("📧 [이메일 보내기](king990630@gmail.com)")
