import pandas as pd
import numpy as np
import re
import random
from datetime import datetime, timedelta
import streamlit as st
import seaborn as sns

sns.set_theme(style="whitegrid")

# ==========================================
# 1. ГЕНЕРАЦІЯ ТЕСТОВИХ ДАНИХ
# ==========================================
def generate_logs(n=15000):
    ips = [f"192.168.0.{random.randint(1, 255)}" for _ in range(50)]
    ips += ["45.33.22.11", "185.212.131.44"]  # аномальні

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

    # оптимізація
    df['method'] = df['method'].astype('category')
    df['url'] = df['url'].astype('category')
    df['status'] = df['status'].astype('int16')
    df['size'] = df['size'].astype('int32')

    return df


# ==========================================
# 2. ПАРСИНГ ЛОГІВ
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
    df.dropna(subset=['timestamp'], inplace=True)

    return df


# ==========================================
# 3. ЗАВАНТАЖЕННЯ ВЕЛИКИХ ФАЙЛІВ
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
    results = {}

    results['total'] = len(df)

    results['4xx'] = len(df[df['status'].between(400, 499)])
    results['5xx'] = len(df[df['status'].between(500, 599)])

    results['top_ips'] = df['ip'].value_counts().head(10)
    results['top_urls'] = df['url'].value_counts().head(10)
    results['methods'] = df['method'].value_counts()

    results['hourly'] = df.resample('H', on='timestamp').size()

    results['avg_size'] = df['size'].mean()

    # аномалії
    threshold = df['ip'].value_counts().mean() * 3
    counts = df['ip'].value_counts()
    results['anomalies'] = counts[counts > threshold]

    return results


# ==========================================
# 5. STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Log Analyzer", layout="wide")
st.title("🛡️ Розширений аналізатор мережевих логів")

# Sidebar
st.sidebar.header("⚙️ Керування")

uploaded_file = st.sidebar.file_uploader("Завантаж лог-файл", type=["log", "txt"])

if st.sidebar.button("Згенерувати тестові дані"):
    df = generate_logs(20000)
    st.session_state["df"] = df
    st.sidebar.success("Дані згенеровано!")

# Логіка отримання даних
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

    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Запити", res['total'])
    col2.metric("4xx", res['4xx'], f"{res['4xx']/res['total']:.1%}")
    col3.metric("5xx", res['5xx'], f"{res['5xx']/res['total']:.1%}")
    col4.metric("Сер. розмір", f"{res['avg_size']:.0f} B")

    st.divider()

    # Графіки
    st.subheader("📊 Активність по часу")
    st.line_chart(res['hourly'])

    st.subheader("🌐 Топ IP")
    st.bar_chart(res['top_ips'])

    st.subheader("📄 Топ URL")
    st.bar_chart(res['top_urls'])

    st.subheader("⚙️ HTTP методи")
    st.bar_chart(res['methods'])

    # Аномалії
    st.subheader("🚨 Підозрілі IP")
    if not res['anomalies'].empty:
        st.warning("Виявлено аномальну активність")
        st.bar_chart(res['anomalies'])
    else:
        st.success("Аномалій не виявлено")

    # Таблиця
    if st.checkbox("Показати дані"):
        st.dataframe(df.head(200), use_container_width=True)

else:
    st.info("⬅️ Завантаж файл або згенеруй тестові дані")
