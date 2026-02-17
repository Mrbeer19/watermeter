import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime
import time

# --- Configuration ---
FB_URL = "https://water-meter-63992-default-rtdb.asia-southeast1.firebasedatabase.app"
FB_AUTH = "jDRjGrWe33KlNcSAKal3im182FzZfzUWEREfrIeC"

st.set_page_config(page_title="Smart Water Dashboard", layout="wide")

# ฟังก์ชันคำนวณค่าน้ำขั้นบันได ประเภทที่ 1 (ที่พักอาศัย)
def calculate_progressive_rate(litres, service_fee):
    units = litres / 1000  #
    price = 0
    # ตารางขั้นบันได [หน่วย, ราคา]
    steps = [
        (30, 8.50), (10, 10.03), (10, 10.35), (10, 10.68), (10, 11.00),
        (10, 11.33), (10, 12.50), (10, 12.82), (20, 13.15), (40, 13.47),
        (40, 13.80), (float('inf'), 14.45)
    ]
    temp_units = units
    for limit, rate in steps:
        if temp_units > 0:
            usage = min(temp_units, limit)
            price += usage * rate
            temp_units -= usage
        else: break
    net_total = price + service_fee
    vat = net_total * 0.07 
    return net_total + vat, units

# --- Styling ---
st.markdown("""
    <style>
    .status-box { padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; color: white; margin-bottom: 10px; }
    .stMetric { background-color: #1A1C24; border-radius: 10px; padding: 15px; border: 1px solid #3D4450; }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    
    # เลือกขนาดมาตรวัด
    meter_config = {
        "1/2 นิ้ว": 25, "3/4 นิ้ว": 40, "1 นิ้ว": 50, "1 1/2 นิ้ว": 80,
        "2 นิ้ว": 300, "3 นิ้ว": 400, "4 นิ้ว": 500, "6 นิ้ว": 900
    }
    selected_size = st.selectbox("ขนาดมาตรวัดน้ำ", list(meter_config.keys()))
    current_fee = meter_config[selected_size]

    st.divider()
    st.subheader("🤖 ระบบอัตโนมัติ")
    
    # ตั้งเวลาปิด
    t_en = st.toggle("เปิดระบบตั้งเวลาปิด")
    t_min = st.number_input("นาทีที่กำหนด", min_value=1, value=10)
    
    # จำกัดปริมาณ
    l_en = st.toggle("เปิดระบบจำกัดลิตร")
    l_limit = st.number_input("ลิตรที่กำหนด", min_value=1.0, value=100.0)
    
    if st.button("บันทึกการตั้งค่าอัตโนมัติ", use_container_width=True):
        requests.put(f"{FB_URL}/control/timerEnable.json?auth={FB_AUTH}", json=t_en)
        requests.put(f"{FB_URL}/control/timerMinutes.json?auth={FB_AUTH}", json=t_min)
        requests.put(f"{FB_URL}/control/limitEnable.json?auth={FB_AUTH}", json=l_en)
        requests.put(f"{FB_URL}/control/limitLitres.json?auth={FB_AUTH}", json=l_limit)
        st.success("บันทึกสำเร็จ!")

    st.divider()
    st.subheader("📏 ปรับขนาดหน้าปัด")
    max_flow_g = st.slider("Max Flow (L/min)", 10, 500, 100)
    max_total_g = st.slider("Max Total (L)", 100, 10000, 1000)

# --- Data Fetching ---
try:
    res = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5)
    fb_online = res.status_code == 200
    db = res.json() if fb_online else {}
    meter = db.get("meter", {})
    esp_online = (time.time() - meter.get("lastUpdate", 0)) < 30
except:
    fb_online, esp_online, meter = False, False, {}

# --- Dashboard View ---
st.title("🚰 Smart Water Meter Full System")

# Status Indicators
c_s1, c_s2, c_s3 = st.columns([1, 1, 3])
with c_s1:
    color = "#28a745" if esp_online else "#dc3545"
    st.markdown(f'<div class="status-box" style="background-color:{color};">DEVICE: {"ONLINE" if esp_online else "OFFLINE"}</div>', unsafe_allow_html=True)
with c_s2:
    color = "#28a745" if fb_online else "#dc3545"
    st.markdown(f'<div class="status-box" style="background-color:{color};">FIREBASE: {"ONLINE" if fb_online else "OFFLINE"}</div>', unsafe_allow_html=True)
with c_s3:
    st.write(f"🕒 อัปเดตล่าสุด: **{datetime.now().strftime('%H:%M:%S')}**")

# Billing Calculation
total_l = meter.get("totalLitres", 0.0)
final_bill, total_u = calculate_progressive_rate(total_l, current_fee)

# Gauges
col_g1, col_g2 = st.columns(2)
with col_g1:
    fig1 = go.Figure(go.Indicator(mode="gauge+number", value=meter.get("flowRate", 0.0),
                     title={'text': "อัตราไหล (L/min)"}, gauge={'axis':{'range':[0, max_flow_g]},'bar':{'color':"#BF40BF"}}))
    st.plotly_chart(fig1, use_container_width=True)
with col_g2:
    fig2 = go.Figure(go.Indicator(mode="gauge+number", value=total_l,
                     title={'text': "ปริมาณสะสม (L)"}, gauge={'axis':{'range':[0, max_total_g]},'bar':{'color':"#0096FF"}}))
    st.plotly_chart(fig2, use_container_width=True)

# Main Metrics
st.divider()
k1, k2, k3 = st.columns(3)
k1.metric("💧 ปริมาณที่ใช้ไป", f"{total_u:.3f} หน่วย (ม³)")
k2.metric("💰 ค่าน้ำรวมสุทธิ", f"{final_bill:.2f} บาท")
k3.metric("📡 สถานะวาล์ว", meter.get("waterStatus", "N/A"))

# Manual Controls
st.subheader("🕹️ แผงควบคุมวาล์ว")
btn_on, btn_off, btn_res = st.columns(3)
if btn_on.button("✅ เปิดน้ำ", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")
if btn_off.button("❌ ปิดน้ำ", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="OFF")
if btn_res.button("♻️ รีเซ็ตลิตรสะสม", use_container_width=True): requests.put(f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}", json=0)

time.sleep(5)
st.rerun()