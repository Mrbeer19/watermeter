import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- Firebase Config ---
FB_URL = "https://water-meter-63992-default-rtdb.asia-southeast1.firebasedatabase.app"
FB_AUTH = "jDRjGrWe33KlNcSAKal3im182FzZfzUWEREfrIeC"

st.set_page_config(page_title="Smart Water Dashboard", layout="wide")

# สูตรคำนวณค่าน้ำขั้นบันได ประเภทที่ 1 (ที่พักอาศัย)
def calculate_progressive_rate(litres, service_fee):
    units = litres / 1000  
    price = 0
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

# --- CSS Dark Theme ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; font-size: 32px !important; font-weight: bold !important; }
    .status-tag { padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 14px; text-align: center; }
    .online { background-color: #006400; color: #90EE90; border: 1px solid #90EE90; }
    .offline { background-color: #4B0000; color: #FFB6C1; border: 1px solid #FFB6C1; }
    div[data-testid="stMetric"] { background-color: #1A1C24; border: 1px solid #3D4450; padding: 15px; border-radius: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- Small Real-time Clock (JavaScript) ---
components.html("""
    <div id="clock" style="color: #00D4FF; font-size: 28px; font-family: sans-serif; font-weight: bold; background: #1A1C24; padding: 5px 15px; border-radius: 10px; border: 1px solid #3D4450; display: inline-block;"></div>
    <script>
    function updateClock() {
        var now = new Date();
        document.getElementById('clock').innerHTML = now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0') + ":" + now.getSeconds().toString().padStart(2, '0');
    }
    setInterval(updateClock, 1000); updateClock();
    </script>
""", height=60)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ Settings")
    meter_config = {"Ø 1/2 นิ้ว": 25.0, "Ø 3/4 นิ้ว": 40.0, "Ø 1 นิ้ว": 50.0, "Ø 1 1/2 นิ้ว": 80.0, "Ø 2 นิ้ว": 300.0}
    selected_size = st.selectbox("ขนาดมาตรวัด", list(meter_config.keys()))
    service_fee = meter_config[selected_size]
    
    st.divider()
    st.subheader("📏 Gauge Scale")
    max_flow_g = st.slider("Max Flow", 10, 500, 100)
    max_total_g = st.slider("Max Total", 100, 10000, 1000)

    st.subheader("🤖 Automation")
    t_en = st.toggle("เปิดระบบตั้งเวลา")
    t_min = st.number_input("จำกัดนาที", min_value=1, value=10)
    l_en = st.toggle("เปิดระบบจำกัดลิตร")
    l_limit = st.number_input("จำกัดลิตร", min_value=1.0, value=100.0)
    
    if st.button("Save Settings", use_container_width=True):
        requests.put(f"{FB_URL}/control/timerEnable.json?auth={FB_AUTH}", json=t_en)
        requests.put(f"{FB_URL}/control/timerMinutes.json?auth={FB_AUTH}", json=t_min)
        requests.put(f"{FB_URL}/control/limitEnable.json?auth={FB_AUTH}", json=l_en)
        requests.put(f"{FB_URL}/control/limitLitres.json?auth={FB_AUTH}", json=l_limit)

# --- Fetch Data & Check Status ---
fb_online, esp_online, meter = False, False, {}
try:
    response = requests.get(f"{FB_URL}/.json?auth={FB_AUTH}", timeout=5)
    if response.status_code == 200:
        fb_online = True
        data = response.json()
        if data:
            meter = data.get("meter", {})
            last_up = meter.get("lastUpdate", 0)
            if last_up > 0 and (time.time() - last_up) < 30: esp_online = True
except: fb_online = False

# --- UI Header (Status Only) ---
st.title("💧 Smart Water Dashboard")
s1, s2 = st.columns([1, 1])
with s1: st.markdown(f'<div class="status-tag {"online" if esp_online else "offline"}">DEVICE: {"ONLINE" if esp_online else "OFFLINE"}</div>', unsafe_allow_html=True)
with s2: st.markdown(f'<div class="status-tag {"online" if fb_online else "offline"}">FIREBASE: {"ONLINE" if fb_online else "OFFLINE"}</div>', unsafe_allow_html=True)

total_l = meter.get("totalLitres", 0.0)
final_bill, total_u = calculate_progressive_rate(total_l, service_fee)

# --- Big Gauges ---
col_g1, col_g2 = st.columns(2)
with col_g1:
    st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=meter.get("flowRate", 0.0), title={'text': "Flow (L/min)", 'font':{'size':24,'color':'white'}}, number={'font':{'size':55,'color':'#00D4FF'}}, gauge={'axis':{'range':[0, max_flow_g]},'bar':{'color':"#BF40BF"}})).update_layout(paper_bgcolor='rgba(0,0,0,0)', height=450))
with col_g2:
    st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=total_l, title={'text': "Total (L)", 'font':{'size':24,'color':'white'}}, number={'font':{'size':55,'color':'#00D4FF'}}, gauge={'axis':{'range':[0, max_total_g]},'bar':{'color':"#0096FF"}})).update_layout(paper_bgcolor='rgba(0,0,0,0)', height=450))

st.divider()
k1, k2, k3 = st.columns(3)
k1.metric("💧 ปริมาณใช้ไป", f"{total_u:.3f} m³")
k2.metric("💰 ค่าน้ำรวม VAT", f"{final_bill:.2f} ฿")
k3.metric("🚰 สถานะวาล์ว", meter.get("waterStatus", "N/A"))

st.subheader("🕹️ Remote Control")
c1, c2, c3 = st.columns(3)
if c1.button("✅ เปิดน้ำ", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="ON")
if c2.button("❌ ปิดน้ำ", use_container_width=True): requests.put(f"{FB_URL}/control/valve.json?auth={FB_AUTH}", json="OFF")
if c3.button("♻️ รีเซ็ตลิตร", use_container_width=True): requests.put(f"{FB_URL}/meter/totalLitres.json?auth={FB_AUTH}", json=0); st.rerun()

time.sleep(5); st.rerun()
