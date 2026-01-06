import streamlit as st
import pandas as pd
import os
import hashlib
import zipfile 
import io      
from datetime import datetime, date, time

# --- 0. [系統級強制設定] 寫入設定檔 (第一道防線) ---
config_dir = ".streamlit"
if not os.path.exists(config_dir):
    os.makedirs(config_dir)
with open(os.path.join(config_dir, "config.toml"), "w", encoding='utf-8') as f:
    f.write('''
[theme]
base="light"
primaryColor="#FF4B4B"
backgroundColor="#FFFFFF"
secondaryBackgroundColor="#F0F2F6"
textColor="#31333F"
''')

# 嘗試載入日曆
try:
    from streamlit_calendar import calendar
except ImportError:
    st.error("請先安裝套件：pip install streamlit-calendar")

# --- 1. 檔案設定 ---
DB_FILE = "gym_lessons.csv"
REQ_FILE = "gym_requests.csv"
STU_FILE = "gym_students.csv"
CAT_FILE = "gym_categories.csv"
COACH_EVT_FILE = "gym_coach_events.csv"
COACH_PASSWORD = "1234"

st.set_page_config(page_title="大胖教練排課表", layout="wide", initial_sidebar_state="collapsed")

# --- 2. [視覺核彈修復] 針對 iOS 深色模式的強制覆蓋 ---
st.markdown("""
    <style>
    /* 1. 強制主視窗背景全白 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }
    [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }
    
    /* 2. 強制全域一般文字變成深黑 */
    h1, h2, h3, p, div, span, label, li {
        color: #31333F !important;
    }
    
    /* 3. [按鈕修復 - 針對您截圖中的"重置系統"、"更新項目"] */
    /* 強制白底、黑字、灰邊框，對抗 iOS 黑底 */
    .stButton > button {
        background-color: #ffffff !important;
        color: #333333 !important;
        border: 1px solid #d1d5db !important;
        font-weight: bold !important;
    }
    /* 按鈕滑鼠懸停效果 */
    .stButton > button:hover {
        border-color: #FF4B4B !important;
        color: #FF4B4B !important;
        background-color: #FFF0F0 !important;
    }

    /* 4. [按鈕修復 - 針對紅色"新增"按鈕] */
    /* 強制紅底、白字 */
    .stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: #ffffff !important;
        border: none !important;
    }
    /* 確保 Primary 按鈕內的文字一定是白色 (覆蓋全域設定) */
    .stButton > button[kind="primary"] * {
        color: #ffffff !important;
    }
    
    /* 5. [選項修復] 單選按鈕 (學員查詢/教練後台) */
    div[data-testid="stRadio"] label p {
        color: #31333F !important;
        font-weight: 900 !important;
        font-size: 1.1rem !important;
    }

    /* 6. [表格修復 - 針對您截圖中的工具列黑底問題] */
    [data-testid="stElementToolbar"] {
        background-color: #ffffff !important;
        color: #333333 !important;
        opacity: 1 !important; /* 強制不透明 */
    }
    [data-testid="stElementToolbar"] button {
        color: #333333 !important;
    }
    
    /* 7. 表格內容 */
    [data-testid="stDataFrame"] {
        background-color: white !important;
        border: 1px solid #ddd !important;
    }

    /* 8. 日曆修復 */
    .fc {
        background-color: #ffffff !important;
        color: #31333F !important;
    }
    .fc-col-header-cell-cushion, .fc-daygrid-day-number {
        color: #31333F !important;
        text-decoration: none !important;
    }
    
    /* 9. 輸入框與選單 */
    input, textarea, select {
        color: #31333F !important;
        background-color: #ffffff !important;
        border: 1px solid #ccc !important;
    }
    /* 下拉選單選項背景 */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #31333F !important;
    }
    
    /* 10. 標題置中 */
    h1 {
        text-align: center;
        margin-bottom: 20px;
        font-family: "Microsoft JhengHei", sans-serif;
    }
    
    /* 11. 卡片樣式 */
    .lesson-card {
        background-color: #f8f9fa !important;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        border-left: 6px solid #ccc;
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# 初始化檔案邏輯 (保持不變)
SCHEMA = {
    DB_FILE: ["日期", "時間", "學員", "課程種類", "備註"],
    REQ_FILE: ["日期", "時間", "姓名", "留言"],
    STU_FILE: ["姓名", "購買堂數", "課程類別", "備註"],
    CAT_FILE: ["類別名稱"],
    COACH_EVT_FILE: ["日期", "時間", "事項", "類型", "備註"]
}
for f, cols in SCHEMA.items():
    if not os.path.exists(f):
        if f == CAT_FILE: pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]}).to_csv(f, index=False)
        else: pd.DataFrame(columns=cols).to_csv(f, index=False)

def load_and_fix_data():
    try:
        df_d = pd.read_csv(DB_FILE)
        df_d["課程種類"] = df_d["課程種類"].fillna("").astype(str)
        for c in SCHEMA[DB_FILE]: 
            if c not in df_d.columns: df_d[c] = ""
        df_d["日期"] = pd.to_datetime(df_d["日期"], errors='coerce').dt.date
    except: df_d = pd.DataFrame(columns=SCHEMA[DB_FILE])

    try:
        df_s = pd.read_csv(STU_FILE)
        if "剩餘堂數" in df_s.columns: df_s.rename(columns={"剩餘堂數": "購買堂數"}, inplace=True)
        if "狀態" in df_s.columns: df_s.rename(columns={"狀態": "課程類別"}, inplace=True)
        for c in SCHEMA[STU_FILE]: 
            if c not in df_s.columns: 
                if c == "購買堂數": df_s[c] = 0
                else: df_s[c] = ""
        # [關鍵] 強制轉文字，確保備註欄可輸入
        df_s["課程類別"] = df_s["課程類別"].fillna("").astype(str)
        df_s["備註"] = df_s["備註"].fillna("").astype(str)
        df_s = df_s[SCHEMA[STU_FILE]]
    except: df_s = pd.DataFrame(columns=SCHEMA[STU_FILE])
    
    try:
        df_r = pd.read_csv(REQ_FILE)
        for c in SCHEMA[REQ_FILE]: 
            if c not in df_r.columns: df_r[c] = ""
    except: df_r = pd.DataFrame(columns=SCHEMA[REQ_FILE])

    try:
        df_c = pd.read_csv(CAT_FILE)
        if df_c.empty: df_c = pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]})
        df_c["類別名稱"] = df_c["類別名稱"].astype(str)
    except: df_c = pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]})

    try:
        df_e = pd.read_csv(COACH_EVT_FILE)
        for c in SCHEMA[COACH_EVT_FILE]: 
            if c not in df_e.columns: df_e[c] = ""
        df_e["日期"] = pd.to_datetime(df_e["日期"], errors='coerce').dt.date
    except: df_e = pd.DataFrame(columns=SCHEMA[COACH_EVT_FILE])

    return df_d, df_s, df_r, df_c, df_e

df_db, df_stu, df_req, df_cat, df_evt = load_and_fix_data()
student_list = df_stu["姓名"].tolist() if not df_stu.empty else []

base_cats = df_cat["類別名稱"].tolist()
db_cats = df_db["課程種類"].unique().tolist()
stu_cats = df_stu["課程類別"].unique().tolist()
raw_all = set(base_cats + db_cats + stu_cats)
ALL_CATEGORIES = [str(x) for x in raw_all if x and str(x).lower() != 'nan' and str(x).strip() != '']
ALL_CATEGORIES.sort()
if not ALL_CATEGORIES: ALL_CATEGORIES = ["(請設定)"]

# ==================== UI 介面 ====================
st.markdown("<h1>🏋️ 大胖教練排課表</h1>", unsafe_allow_html=True)

def get_category_color(cat_name):
    cat_str = str(cat_name)
    if "MA" in cat_str: return "#D32F2F"
    if "S" in cat_str: return "#1976D2"
    if "一般" in cat_str: return "#388E3C"
    palette = ["#F57C00", "#7B1FA2", "#00796B", "#C2185B", "#5D4037", "#303F9F", "#E64A19"]
    hash_val = int(hashlib.sha256(cat_str.encode('utf-8')).hexdigest(), 16)
    return palette[hash_val % len(palette)]

events = []
# 課程
for _, row in df_db.iterrows():
    if pd.isna(row['日期']): continue
    theme_color = get_category_color(row['課程種類'])
    try:
        t_str = str(row['時間'])
        parts = t_str.split(':')
        h = int(parts[0]); m = int(parts[1]) if len(parts) > 1 else 0
        events.append({
            "title": f"{row['學員']}",
            "start": f"{row['日期']}T{h:02d}:{m:02d}:00",
            "end": f"{row['日期']}T{h+1:02d}:{m:02d}:00",
            "backgroundColor": "#FFFFFF",
            "textColor": theme_color,
            "borderColor": theme_color,
        })
    except: continue

# 行程
for _, row in df_evt.iterrows():
    if pd.isna(row['日期']): continue
    evt_color = "#757575" if row['類型'] == "排休" else "#E65100"
    is_all_day = (str(row['時間']) == "全天")
    evt_obj = {"title": f"{row['事項']}", "start": f"{row['日期']}", "backgroundColor": evt_color, "borderColor": evt_color, "textColor": "#FFFFFF", "allDay": is_all_day}
    if not is_all_day:
        try:
            t_str = str(row['時間'])
            parts = t_str.split(':')
            h = int(parts[0]); m = int(parts[1]) if len(parts) > 1 else 0
            evt_obj["start"] = f"{row['日期']}T{h:02d}:{m:02d}:00"
            evt_obj["end"] = f"{row['日期']}T{h+1:02d}:{m:02d}:00"
            evt_obj["allDay"] = False
        except: evt_obj["allDay"] = True
    events.append(evt_obj)

# 假日
holidays = [
    {"start": "2025-12-31", "title": "跨年夜(補)"}, {"start": "2026-01-01", "title": "元旦"},
    {"start": "2026-02-17", "end": "2026-02-23", "title": "春節連假"},
    {"start": "2026-02-28", "title": "228紀念日"}, {"start": "2026-04-04", "end": "2026-04-07", "title": "清明連假"}
]
for h in holidays:
    events.append({"title": h["title"], "start": h["start"], "end": h.get("end"), "allDay": True, "backgroundColor": "#D32F2F", "borderColor": "#D32F2F", "textColor": "#FFFFFF", "display": "block"})

calendar(events=events, options={"initialView": "dayGridMonth", "headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth,listMonth"}}, key="cal_ultimate_fix_v2")
st.divider()

mode = st.radio("", ["🔍 學員查詢", "🔧 教練後台"], horizontal=True)

if mode == "🔍 學員查詢":
    sel_date = st.date_input("查詢日期", date.today())
    day_view = df_db[df_db["日期"] == sel_date].sort_values("時間")
    
    if not day_view.empty:
        for _, row in day_view.iterrows():
            c_code = get_category_color(row['課程種類'])
            # 強制卡片樣式
            st.markdown(f"""
            <div class="lesson-card" style="border-left-color: {c_code}; color: #333 !important;">
                <b style="color:#333">{row['時間']}</b> <span style="color:#333; margin-left:10px">{row['學員']}</span><br>
                <span style="background-color:{c_code}; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em">{row['課程種類']}</span>
            </div>""", unsafe_allow_html=True)
    else: st.info("🍵 本日目前無課程安排")
    
    st.divider()
    if student_list:
        s_name = st.selectbox("查詢餘額 (選擇姓名)", student_list)
        s_data = df_stu[df_stu["姓名"] == s_name].iloc[0]
        used = len(df_db[df_db["學員"] == s_name])
        try: total = int(float(s_data['購買堂數']))
        except: total = 0
        st.write(f"總額: **{total}** | 已上: **{used}** | 餘額: **{total - used}**")
        
    with st.expander("📝 預約/留言"):
        with st.form("req"):
            req_date = st.date_input("預約日期", value=sel_date)
            un = st.text_input("姓名", value=s_name if student_list else "")
            ut = st.selectbox("時段", [f"{h:02d}:00" for h in range(7, 23)])
            um = st.text_area("備註")
            if st.form_submit_button("送出", use_container_width=True):
                pd.concat([df_req, pd.DataFrame([{"日期":str(req_date),"時間":ut,"姓名":un,"留言":um}])]).to_csv(REQ_FILE, index=False)
                st.success("已送出預約")

else:
    pwd = st.text_input("密碼", type="password")
    if pwd == COACH_PASSWORD:
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["排課", "編輯", "名單", "設定", "留言", "📅 行事曆", "📊 報表", "💾 備份"])
        
        with t1:
            with st.container(border=True):
                d = st.date_input("日期", date.today())
                man = st.checkbox("手動時間")
                if man: t = st.time_input("時間", value=time(7, 30)).strftime("%H:%M")
                else: t = st.selectbox("時間", [f"{h:02d}:00" for h in range(7, 23)])
                s = st.selectbox("學員", ["(選學員)"] + student_list)
                def_idx = 0
                if s != "(選學員)":
                    saved = df_stu[df_stu["姓名"] == s].iloc[0]["課程類別"]
                    if saved in ALL_CATEGORIES: def_idx = ALL_CATEGORIES.index(saved)
                cat = st.selectbox("項目", ALL_CATEGORIES, index=def_idx)
                if st.button("➕ 新增", type="primary", use_container_width=True):
                    if s != "(選學員)":
                        pd.concat([df_db, pd.DataFrame([{"日期":d, "時間":t, "學員":s, "課程種類":cat, "備註":""}])], ignore_index=True).to_csv(DB_FILE, index=False)
                        st.success("已排"); st.rerun()

        with t2:
            ed = st.date_input("修課日期", date.today())
            mask = df_db["日期"] == ed
            edited = st.data_editor(df_db[mask], num_rows="dynamic", use_container_width=True,
                column_config={"課程種類": st.column_config.SelectboxColumn("項目", options=ALL_CATEGORIES)})
            if st.button("💾 儲存", key="sv_edit"):
                pd.concat([df_db[~mask], edited], ignore_index=True).to_csv(DB_FILE, index=False); st.rerun()

        with t3:
            st.caption("備註欄可輸入文字")
            # [修正] 確保這裡使用 TextColumn 讓手機可以打字
            estu = st.data_editor(df_stu, num_rows="dynamic", use_container_width=True,
                column_config={
                    "姓名": "姓名",
                    "課程類別": st.column_config.SelectboxColumn("綁定項目", options=ALL_CATEGORIES),
                    "備註": st.column_config.TextColumn("備註 (文字輸入)", help="可輸入中文"),
                    "購買堂數": st.column_config.NumberColumn("購買堂數 (數字)")
                })
            if st.button("💾 更新名單"):
                estu.to_csv(STU_FILE, index=False); st.rerun()

        with t4:
            ecat = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True)
            if st.button("💾 更新項目"): ecat.to_csv(CAT_FILE, index=False); st.rerun()

        with t5:
            st.dataframe(df_req, use_container_width=True)
            if st.button("🗑️ 清空"): pd.DataFrame(columns=["日期", "時間", "姓名", "留言"]).to_csv(REQ_FILE, index=False); st.rerun()

        with t6:
            evt_d = st.date_input("日期", date.today(), key="ed")
            evt_type = st.selectbox("類型", ["排休", "其他"], key="et")
            is_full = st.checkbox("全天", True)
            if not is_full: evt_t = st.time_input("時間", time(12,0)).strftime("%H:%M")
            else: evt_t = "全天"
            evt_c = st.text_input("事項")
            if st.button("➕ 新增"):
                pd.concat([df_evt, pd.DataFrame([{"日期":evt_d,"時間":evt_t,"事項":evt_c,"類型":evt_type,"備註":""}])], ignore_index=True).to_csv(COACH_EVT_FILE, index=False)
                st.rerun()
            st.divider()
            eevt = st.data_editor(df_evt, num_rows="dynamic", use_container_width=True)
            if st.button("💾 儲存行程"): eevt.to_csv(COACH_EVT_FILE, index=False); st.rerun()

        with t7:
            if not df_db.empty:
                df_stat = df_db.copy(); df_stat["日期"] = pd.to_datetime(df_stat["日期"])
                df_stat["月"] = df_stat["日期"].dt.strftime("%Y-%m")
                pivot = df_stat.pivot_table(index="月", columns="課程種類", values="學員", aggfunc="count", fill_value=0)
                st.dataframe(pivot)
            else: st.info("無數據")

        with t8:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "x", zipfile.ZIP_DEFLATED) as zf:
                for f in [DB_FILE, REQ_FILE, STU_FILE, CAT_FILE, COACH_EVT_FILE]:
                    if os.path.exists(f): zf.write(f)
            st.download_button("⬇️ 下載備份", buf.getvalue(), f"backup.zip", "application/zip")
            up = st.file_uploader("上傳還原", type="zip")
            if up and st.button("🚨 還原"):
                with zipfile.ZipFile(up,"r") as z: z.extractall(".")
                st.success("完成"); st.rerun()

    elif pwd != "": st.error("密碼錯誤")

if st.button("⚠️ 重置系統"):
    for f in [DB_FILE, REQ_FILE, STU_FILE, CAT_FILE, COACH_EVT_FILE]:
        if os.path.exists(f): os.remove(f)
    st.rerun()
