import streamlit as st
import requests
import plotly.graph_objects as go
import time

# ---------------- CONFIG ----------------
FB_URL = "https://water-meter-63992-default-rtdb.asia-southeast1.firebasedatabase.app"
FB_AUTH = "YOUR_AUTH_KEY"

st.set_page_config(page_title="Smart Water Meter Pro", layout="wide")

# ---------------- METER CONFIG ----------------
METER_CONFIG = {
    "Ø 1/2 นิ้ว (4 หุน)": 30.0,
    "Ø 3/4 นิ้ว (6 หุน)": 40.0,
    "Ø 1 นิ้ว": 50.0,
    "Ø 1 1/2 นิ้ว": 80.0,
    "Ø 2 นิ้ว": 300.0
}

# ---------------- BILL CALCULATION ----------------
def calculate_pwa_bill(litres, service_fee):
    units = litres / 1000
    water_cost = 0.0

    steps = [
        (10, 10.20),
        (10, 16.00),
        (float('inf'), 19.00)
    ]

    remaining = units

    for limit, rate in steps:
        if remaining <= 0:
            break
        used = min(remaining, limit)
        water_cost += used * rate
        remaining -= used

    water_cost = round(water_cost, 2)
    subtotal = water_cost + service_fee
    vat = round(subtotal * 0.07, 2)
    total = round(subtotal + vat, 2)

    return total, round(units, 3), vat, water_cost

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("⚙️ Meter Settings")

    selected_size = st.selectbox("เลือกขนาดมาตรวัดน้ำ", list(METER_CONFIG.keys()))
    current_service_fee = METER_CONFIG[selected_size]
    st.info(f"ค่าบริการรายเดือน: {current_service_fee} ฿")

    st.divider()
    st.subheader("🤖 Automation Control")

    t_en = st.toggle("เปิดระบบตั้งเวลา (Timer Mode)")
    t_min = st.number_input("จำกัดนาที", min_value=1, value=10)

    l_en = st.toggle("เปิดระบบจำกัดลิตร (Limit Mode)")
    l_limit = st.number_input("จำกัดลิตร", min_value=1.0, value=100.0)

    if st.button("Save Automation Settings", use_container_width=True):
        try:
            requests.put(f"{FB_URL}/control.json?auth={FB_AUTH}", json={
                "timerEnable": t_en,
                "timerMinutes": t_min,
                "limitEnable": l_en,
                "limitLitres": l_limit
            })
            st.success("บันทึกการตั้งค่าสำเร็จ!")
        except:
            st.error("การเชื่อมต่อล้มเหลว")

# ---------------- FETCH DATA ----------------
firebase_online = True

try:
    response = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5)
    response.raise_for_status()
    data = response.json()

    meter = data.get("meter", {})
    total_l = meter.get("totalLitres", 0.0)
    flow_r = meter.get("flowRate", 0.0)
    v_status = meter.get("waterStatus", "OFF")
    last_update = meter.get("lastUpdate", 0)

    is_online = (time.time() - last_update) < 60

except:
    total_l, flow_r, v_status = 0, 0, "N/A"
    is_online = False
    firebase_online = False

# ================== MAIN UI ==================

st.title("💧 Smart Water Meter System")

tab1, tab2 = st.tabs(["💧 Dashboard", "🧮 ตรวจสอบบิล กปภ."])

# ================== TAB 1 ==================
with tab1:

    st.subheader("📡 System Status")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        if is_online:
            st.success("🟢 Device Status: ONLINE")
        else:
            st.error("🔴 Device Status: OFFLINE")

    with col_s2:
        if firebase_online:
            st.success("🟢 Firebase: CONNECTED")
        else:
            st.error("🔴 Firebase: DISCONNECTED")

    st.divider()

    # -------- GAUGE --------
    col_g1, col_g2 = st.columns(2)
    MAX_FLOW = 30

    with col_g1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=max(flow_r, 0),
            number={'suffix': " L/min"},
            title={'text': "Flow Rate"},
            gauge={
                'axis': {'range': [0, MAX_FLOW]},
                'bar': {'color': "#22c55e"},
                'steps': [
                    {'range': [0, MAX_FLOW*0.5], 'color': "#16a34a"},
                    {'range': [MAX_FLOW*0.5, MAX_FLOW*0.8], 'color': "#eab308"},
                    {'range': [MAX_FLOW*0.8, MAX_FLOW], 'color': "#dc2626"},
                ],
            }
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        st.markdown("### 💧 Total Usage")
        st.metric("Total Water Used", f"{total_l:,.2f} Litres")

    st.divider()

    # -------- BILL SUMMARY --------
    final_p, u_total, v_val, w_only = calculate_pwa_bill(
        total_l,
        current_service_fee
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("หน่วยที่ใช้", f"{u_total:.3f} m³")
    m2.metric("ค่าน้ำโดยประมาณ", f"{final_p:,.2f} ฿")
    m3.metric("สถานะวาล์ว", v_status)

    st.divider()

    # -------- MANUAL CONTROL --------
    st.subheader("🕹️ Manual Control")

    c1, c2, c3 = st.columns(3)

    if c1.button("🟢 Open Valve", use_container_width=True):
        requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")

    if c2.button("🔴 Close Valve", use_container_width=True):
        requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="OFF")

    if c3.button("🔄 Reset Meter", use_container_width=True):
        requests.put(f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}", json=0)
        st.rerun()

# ================== TAB 2 ==================
with tab2:

    st.subheader("🧮 เครื่องคิดเลขตรวจสอบบิล กปภ.")

    if "calc_units" not in st.session_state:
        st.session_state.calc_units = 0.0

    if "alert_msg" not in st.session_state:
        st.session_state.alert_msg = None

    col1, col2 = st.columns([2,1])

    with col1:
        calc_units = st.number_input(
            "ใส่จำนวนหน่วยที่ต้องการเช็ค (m³)",
            min_value=0.0,
            value=st.session_state.calc_units,
            key="calc_input"
        )

    with col2:
        if st.button("📡 ดึงข้อมูลจากมิเตอร์", use_container_width=True):
            try:
                response = requests.get(
                    f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}",
                    timeout=5
                )
                latest_litres = response.json()

                if latest_litres is None:
                    raise Exception("No data")

                st.session_state.calc_units = round(latest_litres / 1000, 3)
                st.session_state.alert_msg = ("success", "ดึงข้อมูลจากมิเตอร์เรียบร้อยแล้ว")

            except:
                st.session_state.alert_msg = ("error", "ดึงข้อมูลไม่สำเร็จ")

    # แสดง Alert Box
    if st.session_state.alert_msg:
        alert_type, alert_text = st.session_state.alert_msg
        if alert_type == "success":
            st.success(alert_text)
        else:
            st.error(alert_text)

        # เคลียร์ alert หลังแสดง
        st.session_state.alert_msg = None

    # sync ค่า
    st.session_state.calc_units = st.session_state.get("calc_input", 0.0)

    calc_size = st.selectbox(
        "เลือกขนาดท่อ",
        list(METER_CONFIG.keys())
    )

    if st.button("คำนวณบิล"):
        result, _, vat, water_cost = calculate_pwa_bill(
            st.session_state.calc_units * 1000,
            METER_CONFIG[calc_size]
        )

        st.markdown(f"## 💰 ยอดสุทธิ: {result:,.2f} บาท")
        st.write(
            f"ค่าน้ำ: {water_cost:.2f} | "
            f"ค่าบริการ: {METER_CONFIG[calc_size]} | "
            f"VAT 7%: {vat:.2f}"
        )

# ---------------- AUTO REFRESH ----------------
time.sleep(5)
st.rerun()
