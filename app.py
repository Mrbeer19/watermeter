import streamlit as st
import requests
import plotly.graph_objects as go
import time

# ---------------- CONFIG ----------------
FB_URL = "https://water-meter-63992-default-rtdb.asia-southeast1.firebasedatabase.app"
FB_AUTH = "jDRjGrWe33KlNcSAKal3im182FzZfzUWEREfrIeC"

st.set_page_config(page_title="Smart Water Meter Pro", layout="wide")

METER_CONFIG = {
    "Ø 1/2 นิ้ว (4 หุน)": 30.0,
    "Ø 3/4 นิ้ว (6 หุน)": 40.0,
    "Ø 1 นิ้ว": 50.0,
    "Ø 1 1/2 นิ้ว": 80.0,
    "Ø 2 นิ้ว": 300.0
}

def calculate_pwa_bill(litres, service_fee):
    units = litres / 1000
    water_cost = 0.0
    steps = [(10, 10.20), (10, 16.00), (float('inf'), 19.00)]
    remaining = units
    for limit, rate in steps:
        if remaining <= 0: break
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
                "timerEnable": t_en, "timerMinutes": t_min,
                "limitEnable": l_en, "limitLitres": l_limit,
                "serviceFee": current_service_fee
            })
            st.success("บันทึกการตั้งค่าสำเร็จ!")
        except: st.error("การเชื่อมต่อล้มเหลว")

# ---------------- FETCH DATA & FIX ONLINE STATUS ----------------
try:
    response = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5).json()
    meter = response.get("meter", {})
    total_l = meter.get("totalLitres", 0.0)
    flow_r = meter.get("flowRate", 0.0)
    v_status = meter.get("waterStatus", "OFF")
    
    # ดึงค่า Timestamp (Firebase มักส่งมาเป็นมิลลิวินาที)
    last_update_ms = meter.get("lastUpdate", 0)
    
    # สูตรเช็ค Online: ถ้าเวลาปัจจุบัน (ms) ห่างจาก lastUpdate ไม่เกิน 60 วินาที (60000 ms)
    # เราใช้เวลาจาก Server (โดยประมาณผ่าน time.time()) มาเปรียบเทียบ
    current_time_ms = time.time() * 1000
    is_online = (current_time_ms - last_update_ms) < 60000 
except:
    total_l, flow_r, v_status, is_online = 0, 0, "N/A", False

# ================== MAIN UI ==================
st.title("💧 Smart Water Meter System")
tab1, tab2 = st.tabs(["💧 Dashboard", "🧮 ตรวจสอบบิล กปภ."])

with tab1:
    col_s1, col_s2 = st.columns(2)
    with col_s1: 
        if is_online: st.success("🟢 Device Status: ONLINE")
        else: st.error("🔴 Device Status: OFFLINE")
    with col_s2: st.success("🟢 Firebase: CONNECTED")

    st.divider()
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=max(flow_r, 0), number={'suffix': " L/min"},
            title={'text': "Flow Rate"}, gauge={'axis': {'range': [0, 30]}, 'bar': {'color': "#22c55e"}}))
        st.plotly_chart(fig, use_container_width=True)
    with col_g2:
        st.markdown("### 💧 Total Usage")
        st.metric("Total Water Used", f"{total_l:,.2f} Litres")

    st.divider()
    final_p, u_total, v_val, w_only = calculate_pwa_bill(total_l, current_service_fee)

    # ส่งค่าบิลที่คำนวณแล้วไปให้ ESP8266
    try:
        requests.put(f"{FB_URL}/meter/calculatedBill.json?auth={FB_AUTH}", json=final_p)
    except: pass

    m1, m2, m3 = st.columns(3)
    m1.metric("หน่วยที่ใช้", f"{u_total:.3f} m³")
    m2.metric("ค่าน้ำโดยประมาณ", f"{final_p:,.2f} ฿")
    m3.metric("สถานะวาล์ว", v_status)

    st.divider()
    st.subheader("🕹️ Manual Control")
    c1, c2, c3 = st.columns(3)
    if c1.button("🟢 Open Valve", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")
    if c2.button("🔴 Close Valve", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="OFF")
    if c3.button("🔄 Reset Meter", use_container_width=True): 
        requests.put(f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}", json=0)
        st.rerun()

with tab2:
    st.subheader("🧮 เครื่องคิดเลขตรวจสอบบิล กปภ.")
    calc_units = st.number_input("จำนวนหน่วย (m³)", min_value=0.0, step=0.1)
    calc_size = st.selectbox("ขนาดท่อ", list(METER_CONFIG.keys()))
    if st.button("คำนวณบิล"):
        res, _, vat, w_cost = calculate_pwa_bill(calc_units * 1000, METER_CONFIG[calc_size])
        st.markdown(f"## 💰 ยอดสุทธิ: {res:,.2f} บาท")

time.sleep(5)
st.rerun()
