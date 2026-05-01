import pandas as pd
import numpy as np
import re
import random
from datetime import datetime, timedelta
import streamlit as st
import seaborn as sns

sns.set_theme(style="whitegrid")

# ==========================================
# 🎨 СТИЛІЗАЦІЯ
# ==========================================
st.markdown("""
<style>
.main {background-color: #f5f7fb;}

.title {
    font-size: 40px;
    font-weight: 700;
    color: #2b2d42;
}

.subtitle {
    font-size: 16px;
    color: #6c757d;
    margin-bottom: 20px;
}

.metric-card {
    background: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    text-align: center;
}

.metric-title {
    font-size: 14px;
    color: gray;
}

.metric-value {
    font-size: 28px;
    font-weight: bold;
    color: #2b2d42;
}

.block {
    background: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    margin-top: 20px;
}

.stButton>button {
    border-radius: 10px;
    height: 45px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. ГЕНЕРАЦІЯ ДАНИХ
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
# 5. UI
# ==========================================
st.markdown('<div class="title">🛡️ Розширений аналізатор мережевих логів</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Агрегація та візуалізація логів (Pandas)</div>', unsafe_allow_html=True)

st.sidebar.header("⚙️ Керування")
uploaded_file = st.sidebar.file_uploader("Завантаж лог-файл", type=["log", "txt"])

if st.sidebar.button("Згенерувати тестові дані"):
    st.session_state["df"] = generate_logs(20000)

df = None
if uploaded_file:
    df = load_large_log(uploaded_file)
    st.session_state["df"] = df
elif "df" in st.session_state:
    df = st.session_state["df"]

# ==========================================
# 6. ВІДОБРАЖЕННЯ
# ==========================================
if df is not None and not df.empty:
    res = analyze(df)

    col1, col2, col3, col4 = st.columns(4)

    col1.markdown(f"<div class='metric-card'><div class='metric-title'>Запити</div><div class='metric-value'>{res['total']}</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='metric-card'><div class='metric-title'>4xx</div><div class='metric-value'>{res['4xx']}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='metric-card'><div class='metric-title'>5xx</div><div class='metric-value'>{res['5xx']}</div></div>", unsafe_allow_html=True)
    col4.markdown(f"<div class='metric-card'><div class='metric-title'>Сер. розмір</div><div class='metric-value'>{res['avg_size']:.0f} B</div></div>", unsafe_allow_html=True)

    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("📊 Активність")
    st.line_chart(res['hourly'])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("🌐 Топ IP")
    st.bar_chart(res['top_ips'])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("📄 Топ URL")
    st.bar_chart(res['top_urls'])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("⚙️ Методи")
    st.bar_chart(res['methods'])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("🚨 Аномалії")
    if not res['anomalies'].empty:
        st.error("Виявлено підозрілу активність")
        st.bar_chart(res['anomalies'])
    else:
        st.success("Аномалій не виявлено")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("⬅️ Завантаж файл або згенеруй тестові дані")
