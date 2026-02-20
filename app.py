import streamlit as st
import requests
import plotly.graph_objects as go
import time

# ---------------- CONFIG ----------------
FB_URL = "https://water-meter-63992-default-rtdb.asia-southeast1.firebasedatabase.app"
FB_AUTH = "jDRjGrWe33KlNcSAKal3im182FzZfzUWEREfrIeC" # ใช้ Key จากโค้ด ESP ของคุณ

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

# ---------------- SIDEBAR & DATA FETCH ----------------
with st.sidebar:
    st.header("⚙️ Meter Settings")
    selected_size = st.selectbox("เลือกขนาดมาตรวัดน้ำ", list(METER_CONFIG.keys()))
    current_service_fee = METER_CONFIG[selected_size]
    
    if st.button("Save Automation Settings"):
        # บันทึก Service Fee ลงไปด้วยเพื่อให้ระบบสมบูรณ์
        requests.put(f"{FB_URL}/control/serviceFee.json?auth={FB_AUTH}", json=current_service_fee)
        st.success("บันทึกสำเร็จ!")

# ดึงข้อมูลจาก Firebase
try:
    response = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5).json()
    meter = response.get("meter", {})
    total_l = meter.get("totalLitres", 0.0)
    flow_r = meter.get("flowRate", 0.0)
    v_status = meter.get("waterStatus", "OFF")
except:
    total_l, flow_r, v_status = 0, 0, "OFF"

# ---------------- MAIN UI & CALCULATION ----------------
st.title("💧 Smart Water Meter System")

final_p, u_total, v_val, w_only = calculate_pwa_bill(total_l, current_service_fee)

# >>> ส่วนสำคัญ: ส่งค่าที่คำนวณได้กลับไปที่ Firebase เพื่อให้ ESP8266 ดึงไปโชว์ <<<
requests.put(f"{FB_URL}/meter/calculatedBill.json?auth={FB_AUTH}", json=final_p)

# ส่วนการแสดงผล Dashboard (ย่อมาจากโค้ดเดิมของคุณ)
m1, m2, m3 = st.columns(3)
m1.metric("หน่วยที่ใช้", f"{u_total:.3f} m³")
m2.metric("ค่าน้ำโดยประมาณ", f"{final_p:,.2f} ฿")
m3.metric("สถานะวาล์ว", v_status)

# ปุ่มควบคุมวาล์ว (ตัวอย่าง)
if st.button("🟢 Open Valve"):
    requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")

# Auto Refresh
time.sleep(2)
st.rerun()import streamlit as st
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
    
    subtotal = round(water_cost, 2) + service_fee
    vat = round(subtotal * 0.07, 2)
    total = round(subtotal + vat, 2)
    return total, round(units, 3), vat, round(water_cost, 2)

# ---------------- FETCH DATA ----------------
try:
    fb_data = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5).json()
    meter = fb_data.get("meter", {})
    total_l = meter.get("totalLitres", 0.0)
    flow_r = meter.get("flowRate", 0.0)
    v_status = meter.get("waterStatus", "OFF")
    control = fb_data.get("control", {})
except:
    total_l, flow_r, v_status, control = 0, 0, "OFF", {}

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("⚙️ Settings")
    selected_size = st.selectbox("เลือกขนาดมาตรวัดน้ำ", list(METER_CONFIG.keys()))
    current_fee = METER_CONFIG[selected_size]
    
    st.divider()
    st.subheader("🤖 Automation")
    t_en = st.toggle("Timer Mode", value=control.get("timerEnable", False))
    t_min = st.number_input("จำกัดนาที", value=control.get("timerMinutes", 10))
    l_en = st.toggle("Limit Mode", value=control.get("limitEnable", False))
    l_limit = st.number_input("จำกัดลิตร", value=control.get("limitLitres", 100.0))

    if st.button("Save Settings", use_container_width=True):
        requests.put(f"{FB_URL}/control.json?auth={FB_AUTH}", json={
            "timerEnable": t_en, "timerMinutes": t_min,
            "limitEnable": l_en, "limitLitres": l_limit,
            "serviceFee": current_fee
        })
        st.success("Saved!")

# ---------------- MAIN UI ----------------
st.title("💧 Smart Water Meter System")
final_p, u_total, v_val, w_only = calculate_pwa_bill(total_l, current_fee)

# ส่งค่าเงินไปให้ ESP8266
requests.put(f"{FB_URL}/meter/calculatedBill.json?auth={FB_AUTH}", json=final_p)

tab1, tab2 = st.tabs(["Dashboard", "Bill Calculator"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=flow_r, title={'text': "Flow Rate (L/min)"},
            gauge={'axis': {'range': [0, 30]}, 'bar': {'color': "#22c55e"}}
        ))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.metric("Total Usage", f"{total_l:,.2f} Litres")
        st.metric("Estimated Bill", f"{final_p:,.2f} ฿")
        st.write(f"สถานะวาล์ว: {v_status}")

    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("🟢 Open Valve", use_container_width=True):
        requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")
    if c2.button("🔴 Close Valve", use_container_width=True):
        requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="OFF")
    if c3.button("🔄 Reset", use_container_width=True):
        requests.put(f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}", json=0)

time.sleep(2)
st.rerun()
