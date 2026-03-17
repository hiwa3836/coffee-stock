import streamlit as st
import pandas as pd
import time

# ==========================================
# 1. 모바일 최적화 CSS 주입 (Sticky Bottom Bar & Card UI)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* 하단 고정 액션 바 (FAB/Sticky Bar) */
        .sticky-bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: var(--background-color, #ffffff);
            padding: 16px 20px;
            box-shadow: 0px -4px 12px rgba(0, 0, 0, 0.1);
            z-index: 99999;
            border-top: 1px solid #e0e0e0;
        }
        /* 기본 Streamlit 여백 및 푸터 제거 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {
            padding-bottom: 100px !important; /* 하단 바 영역 확보 */
            padding-top: 2rem !important;
        }
        /* 카드 UI 스타일링 조율용 클래스 (Streamlit 컨테이너에 완벽히 적용되진 않으나 Vibe 유지) */
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 0.5rem;
            background: #ffffff;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 상태 관리 (State Management) - Optimistic UI
# ==========================================
def init_state(df: pd.DataFrame):
    if "inventory_df" not in st.session_state:
        # DB에서 가져온 원본 데이터
        st.session_state.inventory_df = df.copy()
    if "edits" not in st.session_state:
        # 변경된 내역만 추적 {item_id: new_stock_value}
        st.session_state.edits = {}
    if "page" not in st.session_state:
        st.session_state.page = 1

def update_stock(item_id: int, delta: int, min_val: int = 0):
    """Stepper 버튼 클릭 시 즉각적인 상태 업데이트 (Optimistic Update)"""
    # 현재 값 계산 (수정 내역이 있으면 수정값, 없으면 원본값)
    if item_id in st.session_state.edits:
        current_val = st.session_state.edits[item_id]
    else:
        current_val = st.session_state.inventory_df.loc[
            st.session_state.inventory_df["id"] == item_id, "current_stock"
        ].values[0]

    new_val = current_val + delta
    if new_val < min_val:
        new_val = min_val # 음수 방지

    # 변경 상태 저장
    st.session_state.edits[item_id] = new_val

# ==========================================
# 3. 메인 UI 렌더링
# ==========================================
def main():
    st.set_page_config(page_title="재고 관리", layout="centered", initial_sidebar_state="collapsed")
    inject_custom_css()

    # --- Dummy Data (실제 DB Fetch 로직으로 대체) ---
    dummy_data = {
        "id": [1, 2, 3, 4, 5],
        "category": ["A", "A", "B", "C", "C"],
        "item_name": ["원두 1kg", "우유 1L", "종이컵(대)", "시럽(바닐라)", "빨대"],
        "current_stock": [5, 12, 100, 2, 500],
        "min_stock": [10, 15, 200, 5, 1000],
        "unit": ["포대", "팩", "개", "병", "개"],
        "barcode": ["8801", "8802", "8803", "8804", "8805"]
    }
    df = pd.DataFrame(dummy_data)
    init_state(df)

    st.subheader("📦 모바일 재고 실사")

    # --- 검색 및 스캐너 영역 (Search & Scan) ---
    search_query = st.text_input(
        "🔍 바코드 스캔 또는 품목 검색", 
        placeholder="바코드를 스캔하거나 품목명을 입력하세요...",
        help="블루투스 스캐너나 모바일 키보드를 통해 입력 시 즉시 필터링됩니다."
    )

    # --- 데이터 필터링 ---
    display_df = st.session_state.inventory_df.copy()
    
    if search_query:
        # 바코드 일치 또는 이름 포함으로 필터링
        display_df = display_df[
            display_df["barcode"].str.contains(search_query, na=False) | 
            display_df["item_name"].str.contains(search_query, na=False)
        ]
    
    show_shortage = st.toggle("🚨 부족 품목만 보기")
    if show_shortage:
        # 수정된 재고(edits)를 반영하여 부족 품목 계산
        temp_df = display_df.copy()
        temp_df['active_stock'] = temp_df['id'].map(st.session_state.edits).fillna(temp_df['current_stock'])
        display_df = temp_df[temp_df["active_stock"] <= temp_df["min_stock"]]

    if display_df.empty:
        st.info("조건에 맞는 품목이 없습니다.")
        return

    # --- Pagination (DOM 과부하 방지) ---
    ITEMS_PER_PAGE = 10
    total_pages = (len(display_df) - 1) // ITEMS_PER_PAGE + 1
    
    start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    paged_df = display_df.iloc[start_idx:end_idx]

    # --- Card & Stepper UI 렌더링 ---
    for _, row in paged_df.iterrows():
        item_id = row["id"]
        
        # 현재 화면에 표시할 재고 (수정본 우선)
        display_stock = st.session_state.edits.get(item_id, row["current_stock"])
        
        # 상태 인디케이터
        if display_stock <= row["min_stock"]: status = "🔴"
        elif display_stock <= row["min_stock"] + 2: status = "🟡"
        else: status = "🟢"

        # 카드 컨테이너
        with st.container():
            col1, col2 = st.columns([3, 2], vertical_alignment="center")
            
            with col1:
                st.markdown(f"**{status} {row['item_name']}**")
                st.caption(f"카테고리: {row['category']} | 최소: {row['min_stock']}{row['unit']}")
            
            with col2:
                # Stepper Buttons
                btn_col1, val_col, btn_col2 = st.columns([1, 1.5, 1])
                with btn_col1:
                    st.button("➖", key=f"minus_{item_id}", on_click=update_stock, args=(item_id, -1))
                with val_col:
                    # 중앙에 현재 값 표시 (숫자 직접 입력이 필요하다면 st.number_input 사용 가능하나 터치 친화도를 위해 markdown 사용)
                    st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; padding-top: 5px;'>{int(display_stock)}</div>", unsafe_allow_html=True)
                with btn_col2:
                    st.button("➕", key=f"plus_{item_id}", on_click=update_stock, args=(item_id, 1))
            st.divider() # 카드 구분선

    # 페이지네이션 컨트롤
    if total_pages > 1:
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            if st.button("⬅️ 이전", disabled=st.session_state.page == 1):
                st.session_state.page -= 1
                st.rerun()
        with p_col2:
            st.markdown(f"<div style='text-align: center; margin-top: 10px;'>{st.session_state.page} / {total_pages}</div>", unsafe_allow_html=True)
        with p_col3:
            if st.button("다음 ➡️", disabled=st.session_state.page == total_pages):
                st.session_state.page += 1
                st.rerun()

    # --- 하단 고정 바 (Sticky Bottom Bar) ---
    has_changes = len(st.session_state.edits) > 0
    
    # HTML/CSS로 위치를 잡고, 빈 컨테이너를 이용해 Streamlit 컴포넌트를 주입하는 트릭
    st.markdown('<div class="sticky-bottom-bar">', unsafe_allow_html=True)
    
    save_col1, save_col2 = st.columns([1, 2])
    with save_col1:
        st.markdown(f"<div style='padding-top: 10px; font-weight: bold;'>📝 변경: {len(st.session_state.edits)}건</div>", unsafe_allow_html=True)
    with save_col2:
        if st.button("✅ 변경 승인 및 저장", type="primary", use_container_width=True, disabled=not has_changes):
            with st.spinner("DB 반영 중..."):
                # TODO: 실제 DB 업데이트 로직 연동
                # process_inventory_changes(st.session_state.edits)
                time.sleep(1) # 모의 지연
                
                # 업데이트 완료 후 원본 데이터 갱신 및 상태 초기화
                for i_id, new_val in st.session_state.edits.items():
                    st.session_state.inventory_df.loc[st.session_state.inventory_df["id"] == i_id, "current_stock"] = new_val
                
                st.session_state.edits = {} # 큐 비우기
                st.success("업데이트 완료!")
                time.sleep(1)
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
