import streamlit as st
import pandas as pd
import os
import hashlib
import zipfile 
import io      
from datetime import datetime, date, time

# 嘗試載入日曆組件
try:
    from streamlit_calendar import calendar
except ImportError:
    st.error("請先安裝套件：pip install streamlit-calendar")

# --- 1. 檔案設定 (固定檔名 - 保持不變) ---
DB_FILE = "gym_lessons.csv"
REQ_FILE = "gym_requests.csv"
STU_FILE = "gym_students.csv"
CAT_FILE = "gym_categories.csv"
COACH_EVT_FILE = "gym_coach_events.csv"
COACH_PASSWORD = "1234"

# [修改 1] 標題設定變更
st.set_page_config(page_title="大胖教練排課表", layout="wide", initial_sidebar_state="collapsed")

# [修改 2] 版面風格優化 (注入 CSS)
st.markdown("""
    <style>
    /* 全域字體與背景微調 */
    .stApp {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        font-family: "Microsoft JhengHei", sans-serif;
        font-weight: 700 !important;
        color: #2c3e50;
    }
    
    /* 按鈕樣式優化 */
    .stButton>button {
        border-radius: 12px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 學員課程卡片樣式 */
    .lesson-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        border-left-width: 6px;
        border-left-style: solid;
        margin-bottom: 12px;
        transition: transform 0.2s;
    }
    .lesson-card:hover {
        transform: scale(1.01);
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .time-badge {
        font-size: 1.1em;
        font-weight: bold;
        color: #333;
    }
    .student-name {
        font-size: 1.1em;
        font-weight: bold;
        margin-left: 10px;
    }
    .cat-tag {
        display: inline-block;
        margin-top: 5px;
        font-size: 0.85em;
        padding: 2px 8px;
        border-radius: 4px;
        color: white;
        background-color: #555;
    }
    </style>
""", unsafe_allow_html=True)

# 欄位定義
SCHEMA = {
    DB_FILE: ["日期", "時間", "學員", "課程種類", "備註"],
    REQ_FILE: ["日期", "時間", "姓名", "留言"],
    STU_FILE: ["姓名", "購買堂數", "課程類別", "備註"],
    CAT_FILE: ["類別名稱"],
    COACH_EVT_FILE: ["日期", "時間", "事項", "類型", "備註"]
}

# 初始化檔案
for f, cols in SCHEMA.items():
    if not os.path.exists(f):
        if f == CAT_FILE:
            pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]}).to_csv(f, index=False)
        else:
            pd.DataFrame(columns=cols).to_csv(f, index=False)

# --- 資料讀取與自動修復 (防崩潰核心 - 保持不變) ---
def load_and_fix_data():
    # 1. 讀取課程
    try:
        df_d = pd.read_csv(DB_FILE)
        if "課程種類" in df_d.columns:
            df_d["課程種類"] = df_d["課程種類"].fillna("").astype(str)
        for c in SCHEMA[DB_FILE]: 
            if c not in df_d.columns: df_d[c] = ""
        df_d["日期"] = pd.to_datetime(df_d["日期"], errors='coerce').dt.date
    except: df_d = pd.DataFrame(columns=SCHEMA[DB_FILE])

    # 2. 讀取學員
    try:
        df_s = pd.read_csv(STU_FILE)
        if "剩餘堂數" in df_s.columns and "購買堂數" not in df_s.columns:
            df_s.rename(columns={"剩餘堂數": "購買堂數"}, inplace=True)
        if "狀態" in df_s.columns and "課程類別" not in df_s.columns:
            df_s.rename(columns={"狀態": "課程類別"}, inplace=True)
        if "課程類別" in df_s.columns:
            df_s["課程類別"] = df_s["課程類別"].fillna("").astype(str)
        for c in SCHEMA[STU_FILE]: 
            if c not in df_s.columns: 
                if c == "購買堂數": df_s[c] = 0
                else: df_s[c] = ""
        df_s = df_s[SCHEMA[STU_FILE]]
    except: df_s = pd.DataFrame(columns=SCHEMA[STU_FILE])

    # 3. 讀取留言
    try:
        df_r = pd.read_csv(REQ_FILE)
        for c in SCHEMA[REQ_FILE]: 
            if c not in df_r.columns: df_r[c] = ""
    except: df_r = pd.DataFrame(columns=SCHEMA[REQ_FILE])

    # 4. 讀取類別
    try:
        df_c = pd.read_csv(CAT_FILE)
        if df_c.empty or "類別名稱" not in df_c.columns:
            df_c = pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]})
        df_c["類別名稱"] = df_c["類別名稱"].astype(str)
    except: df_c = pd.DataFrame({"類別名稱": ["MA 體態", "S 專項"]})

    # 5. 行事曆
    try:
        df_e = pd.read_csv(COACH_EVT_FILE)
        for c in SCHEMA[COACH_EVT_FILE]:
            if c not in df_e.columns: df_e[c] = ""
        df_e["日期"] = pd.to_datetime(df_e["日期"], errors='coerce').dt.date
    except: df_e = pd.DataFrame(columns=SCHEMA[COACH_EVT_FILE])

    return df_d, df_s, df_r, df_c, df_e

df_db, df_stu, df_req, df_cat, df_evt = load_and_fix_data()

student_list = df_stu["姓名"].tolist() if not df_stu.empty else []

# --- 關鍵修復：建立絕對安全的下拉選單 (保持不變) ---
base_cats = df_cat["類別名稱"].tolist()
db_cats = df_db["課程種類"].unique().tolist()
stu_cats = df_stu["課程類別"].unique().tolist()

raw_all = set(base_cats + db_cats + stu_cats)
ALL_CATEGORIES = [str(x) for x in raw_all if x and str(x).lower() != 'nan' and str(x).strip() != '']
ALL_CATEGORIES.sort()

if not ALL_CATEGORIES:
    ALL_CATEGORIES = ["(請設定)"]

# ==================== 2. 全域大日曆 ====================
# [修改 3] 標題置中且加大
st.markdown("<h1 style='text-align: center; margin-bottom: 20px;'>🏋️ 大胖教練排課表</h1>", unsafe_allow_html=True)

def get_category_color(cat_name):
    cat_str = str(cat_name)
    if "MA" in cat_str: return "#D32F2F"
    if "S" in cat_str: return "#1976D2"
    if "一般" in cat_str: return "#388E3C"
    
    palette = ["#F57C00", "#7B1FA2", "#00796B", "#C2185B", "#5D4037", "#303F9F", "#E64A19"]
    hash_val = int(hashlib.sha256(cat_str.encode('utf-8')).hexdigest(), 16)
    return palette[hash_val % len(palette)]

events = []

# A. 課程
for _, row in df_db.iterrows():
    if pd.isna(row['日期']): continue
    theme_color = get_category_color(row['課程種類'])
    try:
        t_str = str(row['時間'])
        parts = t_str.split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        
        start_iso = f"{row['日期']}T{h:02d}:{m:02d}:00"
        end_h = h + 1
        end_iso = f"{row['日期']}T{end_h:02d}:{m:02d}:00"
        
        events.append({
            "title": f"{row['學員']}",
            "start": start_iso,
            "end": end_iso,
            "backgroundColor": "#FFFFFF",
            "textColor": theme_color,
            "borderColor": theme_color,
        })
    except: continue

# B. 行事曆
for _, row in df_evt.iterrows():
    if pd.isna(row['日期']): continue
    
    if row['類型'] == "排休":
        evt_color = "#757575"
    else:
        evt_color = "#E65100"
    
    is_all_day = (str(row['時間']) == "全天")
    
    evt_obj = {
        "title": f"{row['事項']}",
        "start": f"{row['日期']}",
        "backgroundColor": evt_color,
        "borderColor": evt_color,
        "textColor": "#FFFFFF",
        "allDay": is_all_day
    }
    
    if not is_all_day:
        try:
            t_str = str(row['時間'])
            parts = t_str.split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            
            evt_obj["start"] = f"{row['日期']}T{h:02d}:{m:02d}:00"
            evt_obj["end"] = f"{row['日期']}T{h+1:02d}:{m:02d}:00"
            evt_obj["allDay"] = False
        except: 
            evt_obj["allDay"] = True
            
    events.append(evt_obj)

# C. 假日
holidays = [
    {"start": "2025-12-31", "title": "跨年夜(補)"},
    {"start": "2026-01-01", "title": "元旦"},
    {"start": "2026-02-17", "end": "2026-02-23", "title": "春節連假"},
    {"start": "2026-02-28", "title": "228紀念日"},
    {"start": "2026-04-04", "end": "2026-04-07", "title": "清明連假"},
    {"start": "2025-01-01", "title": "元旦"},
    {"start": "2025-01-25", "end": "2025-02-03", "title": "春節"},
]
for h in holidays:
    events.append({
        "title": h["title"], "start": h["start"], "end": h.get("end"), "allDay": True,
        "backgroundColor": "#D32F2F", "borderColor": "#D32F2F", "textColor": "#FFFFFF", "display": "block",
    })

calendar_options = {
    "editable": False,
    "headerToolbar": {
        "left": "prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay,listMonth" 
    },
    "locale": "en", 
    "buttonText": {
        "today": "今天", "month": "月", "week": "周", "day": "日", "list": "清單"
    },
    "dayHeaderFormat": { "weekday": "short" }, 
    "initialView": "dayGridMonth",
    "height": 550,
    "slotMinTime": "06:00:00", "slotMaxTime": "23:00:00", "firstDay": 1,
    "eventTimeFormat": { "hour": "2-digit", "minute": "2-digit", "hour12": False },
    "views": {
        "listMonth": { "listDayFormat": { "month": "numeric", "day": "numeric", "weekday": "short" } }
    }
}
calendar(events=events, options=calendar_options, key="cal_v34_fix_crash")
st.divider()

# ==================== 3. 身份導覽 ====================
mode = st.radio("", ["🔍 學員查詢", "🔧 教練後台"], horizontal=True)

if mode == "🔍 學員查詢":
    sel_date = st.date_input("查詢日期", date.today())
    day_view = df_db[df_db["日期"] == sel_date].sort_values("時間")
    
    if not day_view.empty:
        for _, row in day_view.iterrows():
            c_code = get_category_color(row['課程種類'])
            # [修改 4] 使用新的 CSS 卡片樣式，更換 HTML 結構
            st.markdown(f"""
            <div class="lesson-card" style="border-left-color: {c_code};">
                <span class="time-badge">🕒 {row['時間']}</span>
                <span class="student-name">👤 {row['學員']}</span>
                <br>
                <span class="cat-tag" style="background-color: {c_code};">📌 {row['課程種類']}</span>
            </div>
            """, unsafe_allow_html=True)
    else: st.info("🍵 本日目前無課程安排")
    
    st.divider()
    if student_list:
        s_name = st.selectbox("查詢餘額 (選擇姓名)", student_list)
        s_data = df_stu[df_stu["姓名"] == s_name].iloc[0]
        used = len(df_db[df_db["學員"] == s_name])
        try: total = int(float(s_data['購買堂數']))
        except: total = 0
        left = total - used
        c1, c2, c3 = st.columns(3)
        c1.metric("總額", total); c2.metric("已上", used); c3.metric("餘額", left)
        
    with st.expander("📝 預約/留言"):
        with st.form("req"):
            req_date = st.date_input("預約日期", value=sel_date)
            un = st.text_input("姓名", value=s_name if student_list else "")
            ut = st.selectbox("時段", [f"{h:02d}:00" for h in range(7, 23)])
            um = st.text_area("備註")
            if st.form_submit_button("送出", use_container_width=True):
                pd.concat([df_req, pd.DataFrame([{"日期":str(req_date),"時間":ut,"姓名":un,"留言":um}])]).to_csv(REQ_FILE, index=False)
                st.success(f"已送出預約：{req_date} {ut}")

else:
    pwd = st.text_input("密碼", type="password")
    if pwd == COACH_PASSWORD:
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["排課", "編輯", "名單", "設定", "留言", "📅 行事曆", "📊 報表", "💾 備份"])
        
        with t1:
            st.caption("🚀 快速排課")
            with st.container(border=True):
                d = st.date_input("日期", date.today())
                
                c_t1, c_t2 = st.columns([3, 1])
                with c_t2:
                    manual_time = st.checkbox("⏳ 手動輸入", help="勾選後可輸入 7:30 等非整點時間")
                with c_t1:
                    if manual_time:
                        t_obj = st.time_input("時間 (請輸入)", value=time(7, 30))
                        t = t_obj.strftime("%H:%M")
                    else:
                        t = st.selectbox("時間", [f"{h:02d}:00" for h in range(7, 23)])
                
                s = st.selectbox("學員", ["(選學員)"] + student_list)
                
                # 選項邏輯：如果學員已有綁定，預設選那個，但也要允許選其他的
                opts = ALL_CATEGORIES
                default_idx = 0
                if s != "(選學員)":
                    rec = df_stu[df_stu["姓名"] == s]
                    if not rec.empty:
                        saved = rec.iloc[0]["課程類別"]
                        if saved and saved in ALL_CATEGORIES:
                            default_idx = ALL_CATEGORIES.index(saved)
                
                cat = st.selectbox("項目", opts, index=default_idx)
                
                if st.button("➕ 新增", type="primary", use_container_width=True):
                    if s != "(選學員)":
                        new_row = pd.DataFrame([{"日期": d, "時間": t, "學員": s, "課程種類": cat, "備註": ""}])
                        updated_df = pd.concat([df_db, new_row], ignore_index=True)
                        updated_df.to_csv(DB_FILE, index=False)
                        st.success(f"已排：{s} ({t})"); st.rerun()
                    else: st.error("未選人")

        with t2:
            st.info("💡 編輯課程")
            ed = st.date_input("修課日期", date.today())
            mask = df_db["日期"] == ed
            
            edited = st.data_editor(
                df_db[mask], num_rows="dynamic", use_container_width=True, 
                column_config={"課程種類": st.column_config.SelectboxColumn("項目", options=ALL_CATEGORIES)}
            )
            if st.button("💾 儲存課程", use_container_width=True):
                pd.concat([df_db[~mask], edited], ignore_index=True).to_csv(DB_FILE, index=False); st.rerun()

        with t3:
            st.caption("設定學員")
            estu = st.data_editor(df_stu, num_rows="dynamic", use_container_width=True, 
                column_config={"姓名":"姓名","課程類別": st.column_config.SelectboxColumn("綁定項目", options=ALL_CATEGORIES)})
            if st.button("💾 更新名單", use_container_width=True):
                estu.to_csv(STU_FILE, index=False); st.rerun()

        with t4:
            st.caption("自訂課程")
            ecat = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True)
            if st.button("💾 更新項目", use_container_width=True):
                ecat.to_csv(CAT_FILE, index=False); st.rerun()

        with t5:
            st.dataframe(df_req, use_container_width=True)
            if st.button("🗑️ 清空", use_container_width=True):
                pd.DataFrame(columns=["日期", "時間", "姓名", "留言"]).to_csv(REQ_FILE, index=False); st.rerun()

        with t6:
            st.subheader("📅 行事曆登記")
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                evt_d = c1.date_input("日期", date.today(), key="evt_d")
                evt_type = c2.selectbox("類型", ["排休", "其他"], key="evt_type")
                is_all_day = c3.checkbox("全天", value=True)
                
                if not is_all_day:
                    man_evt_t = c3.checkbox("手動時間", key="man_evt")
                    if man_evt_t:
                        evt_t_obj = st.time_input("時間", value=time(7, 30), key="evt_t_in")
                        evt_t = evt_t_obj.strftime("%H:%M")
                    else:
                        evt_t = st.selectbox("時間", [f"{h:02d}:00" for h in range(7, 23)], key="evt_t")
                else:
                    evt_t = "全天"
                
                if evt_type == "排休":
                    evt_title = "排休"
                    st.info("📌 已設定為「排休」")
                else:
                    evt_title = st.text_input("請輸入事項說明", placeholder="例如: 看牙醫", key="evt_title")
                
                if st.button("➕ 新增行程", use_container_width=True):
                    if evt_type == "其他" and not evt_title:
                        st.error("請輸入事項說明！")
                    else:
                        new_evt = pd.DataFrame([{"日期": evt_d, "時間": evt_t, "事項": evt_title, "類型": evt_type, "備註": ""}])
                        pd.concat([df_evt, new_evt], ignore_index=True).to_csv(COACH_EVT_FILE, index=False)
                        st.success("已登記！"); st.rerun()
            
            st.divider()
            edited_evt = st.data_editor(df_evt, num_rows="dynamic", use_container_width=True)
            if st.button("💾 儲存行程", use_container_width=True):
                edited_evt.to_csv(COACH_EVT_FILE, index=False); st.success("更新成功"); st.rerun()

        with t7:
            st.subheader("📊 統計報表")
            if not df_db.empty:
                df_stat = df_db.copy()
                df_stat["日期"] = pd.to_datetime(df_stat["日期"])
                df_stat["月份"] = df_stat["日期"].dt.strftime("%Y-%m")
                pivot = df_stat.pivot_table(index="月份", columns="課程種類", values="學員", aggfunc="count", fill_value=0)
                pivot["👉 總計"] = pivot.sum(axis=1)
                st.dataframe(pivot.sort_index(ascending=False), use_container_width=True)
                st.bar_chart(pivot["👉 總計"])
            else: st.info("尚無數據")

        with t8:
            st.subheader("💾 備份管理")
            c1, c2 = st.columns(2)
            with c1:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "x", zipfile.ZIP_DEFLATED) as zf:
                    for f in [DB_FILE, REQ_FILE, STU_FILE, CAT_FILE, COACH_EVT_FILE]:
                        if os.path.exists(f): zf.write(f)
                st.download_button("⬇️ 下載備份", buf.getvalue(), f"backup_{datetime.now().strftime('%m%d')}.zip", "application/zip", "primary")
            with c2:
                up_zip = st.file_uploader("上傳還原", type="zip")
                if up_zip and st.button("🚨 還原"):
                    with zipfile.ZipFile(up_zip, "r") as z: z.extractall(".")
                    st.success("成功！"); st.rerun()

    elif pwd != "": st.error("密碼錯誤")

if st.button("⚠️ 重置"):
    for f in [DB_FILE, REQ_FILE, STU_FILE, CAT_FILE, COACH_EVT_FILE]:
        if os.path.exists(f): os.remove(f)
    st.rerun()