import pandas as pd
import numpy as np
import re
import random
from datetime import datetime, timedelta
import streamlit as st
import seaborn as sns
import plotly.express as px
import time

sns.set_theme(style="whitegrid")

# ==========================================
# 🎨 СТИЛІ
# ==========================================
st.markdown("""
<style>
.main {background-color: #f5f7fb;}

.title {font-size: 40px; font-weight: 700; color: #2b2d42;}
.subtitle {font-size: 16px; color: #6c757d; margin-bottom: 20px;}

.metric-card {
    background: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    text-align: center;
}

.metric-title {font-size: 14px; color: gray;}
.metric-value {font-size: 28px; font-weight: bold; color: #2b2d42;}

.block {
    background: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    margin-top: 20px;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. ГЕНЕРАЦІЯ
# ==========================================
def generate_logs(n=15000):
    ips = [f"192.168.0.{random.randint(1, 255)}" for _ in range(50)]
    ips += ["45.33.22.11", "185.212.131.44"]

    methods = ["GET", "POST", "HEAD"]
    urls = ["/", "/login", "/api", "/admin", "/config"]
    statuses = [200, 200, 200, 301, 404, 500, 403]

    now = datetime.now()

    data = []
    for _ in range(n):
        data.append({
            "ip": random.choice(ips),
            "timestamp": now - timedelta(seconds=random.randint(0, 86400)),
            "method": random.choice(methods),
            "url": random.choice(urls),
            "status": random.choice(statuses),
            "size": random.randint(200, 5000)
        })

    df = pd.DataFrame(data)
    df['method'] = df['method'].astype('category')
    df['url'] = df['url'].astype('category')
    df['status'] = df['status'].astype('int16')
    df['size'] = df['size'].astype('int32')

    return df

# ==========================================
# 2. ПАРСИНГ
# ==========================================
log_pattern = re.compile(
    r'(?P<ip>\d+\.\d+\.\d+\.\d+) - - \[(?P<timestamp>.*?)\] '
    r'"(?P<method>\w+) (?P<url>.*?) HTTP/.*?" '
    r'(?P<status>\d+) (?P<size>\d+)'
)

def parse_chunk(lines):
    data = []
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        match = log_pattern.search(line)
        if match:
            data.append(match.groupdict())

    df = pd.DataFrame(data)
    if df.empty:
        return df

    df['status'] = df['status'].astype('int16')
    df['size'] = pd.to_numeric(df['size'], errors='coerce').fillna(0).astype('int32')
    df['method'] = df['method'].astype('category')
    df['url'] = df['url'].astype('category')

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    return df

# ==========================================
# 3. ЗАВАНТАЖЕННЯ
# ==========================================
def load_large_log(file, chunk_size=5000):
    chunks = []
    lines = file.readlines()

    for i in range(0, len(lines), chunk_size):
        chunk = parse_chunk(lines[i:i + chunk_size])
        if not chunk.empty:
            chunks.append(chunk)

    if chunks:
        return pd.concat(chunks, ignore_index=True)

    return pd.DataFrame()

# ==========================================
# 4. АНАЛІЗ
# ==========================================
def analyze(df):
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    results = {}
    results['total'] = len(df)
    results['4xx'] = len(df[df['status'].between(400, 499)])
    results['5xx'] = len(df[df['status'].between(500, 599)])
    results['top_ips'] = df['ip'].value_counts().head(10)
    results['top_urls'] = df['url'].value_counts().head(10)
    results['methods'] = df['method'].value_counts()

    df = df.set_index('timestamp')
    results['hourly'] = df.resample('h').size()

    results['avg_size'] = df['size'].mean()

    counts = df['ip'].value_counts()
    threshold = counts.mean() * 3
    results['anomalies'] = counts[counts > threshold]

    return results

# ==========================================
# UI
# ==========================================
st.markdown('<div class="title">🛡️ Аналізатор логів</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Анімований dashboard</div>', unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("Завантаж лог", type=["log","txt"])

if st.sidebar.button("Згенерувати тестові дані"):
    st.session_state["df"] = generate_logs(20000)

df = None
if uploaded_file:
    df = load_large_log(uploaded_file)
    st.session_state["df"] = df
elif "df" in st.session_state:
    df = st.session_state["df"]

# ==========================================
# DASHBOARD
# ==========================================
if df is not None and not df.empty:
    res = analyze(df)

    # Метрики
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f"<div class='metric-card'><div class='metric-title'>Запити</div><div class='metric-value'>{res['total']}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-title'>4xx</div><div class='metric-value'>{res['4xx']}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-title'>5xx</div><div class='metric-value'>{res['5xx']}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='metric-title'>Сер. розмір</div><div class='metric-value'>{res['avg_size']:.0f}</div></div>", unsafe_allow_html=True)

    # 📊 Анімований графік
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("📊 Активність (анімація)")

    df_plot = res['hourly'].reset_index()
    df_plot.columns = ['time','requests']

    fig = px.line(df_plot, x='time', y='requests')
    fig.update_layout(transition_duration=500)

    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 🔴 LIVE режим
    live = st.toggle("🔴 Live режим")

    if live:
        progress = st.progress(0)
        chart = st.empty()

        temp = df.sort_values("timestamp").set_index("timestamp")

        step = max(len(temp)//20, 1)

        for i in range(step, len(temp), step):
            part = temp.iloc[:i]
            series = part.resample('h').size()

            chart.line_chart(series)
            progress.progress(i/len(temp))
            time.sleep(0.2)

    # 🌐 IP
    st.markdown('<div class="block">', unsafe_allow_html=True)
    ip_df = res['top_ips'].reset_index()
    ip_df.columns=['ip','count']
    fig2 = px.bar(ip_df, x='ip', y='count')
    st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("Завантаж файл або згенеруй дані")
