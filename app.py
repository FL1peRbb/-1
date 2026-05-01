import pandas as pd
import numpy as np
import re
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

sns.set_theme(style="whitegrid")

# ==========================================
# 1. ПАРСИНГ ЛОГІВ (ОПТИМІЗОВАНИЙ)
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

    # Оптимізація типів
    df['status'] = df['status'].astype('int16')
    df['size'] = pd.to_numeric(df['size'], errors='coerce').fillna(0).astype('int32')
    df['method'] = df['method'].astype('category')
    df['url'] = df['url'].astype('category')

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True)

    return df

# ==========================================
# 2. ЗАВАНТАЖЕННЯ ВЕЛИКИХ ФАЙЛІВ (CHUNKS)
# ==========================================
def load_large_log(file, chunk_size=5000):
    chunks = []
    lines = file.readlines()

    for i in range(0, len(lines), chunk_size):
        chunk = parse_chunk(lines[i:i+chunk_size])
        if not chunk.empty:
            chunks.append(chunk)

    if chunks:
        return pd.concat(chunks, ignore_index=True)
    return pd.DataFrame()

# ==========================================
# 3. АНАЛІЗ ДАНИХ (РОЗШИРЕНИЙ)
# ==========================================
def analyze(df):
    results = {}

    results['total'] = len(df)

    # Помилки
    results['4xx'] = len(df[df['status'].between(400, 499)])
    results['5xx'] = len(df[df['status'].between(500, 599)])

    # Топ IP
    results['top_ips'] = df['ip'].value_counts().head(10)

    # Топ URL
    results['top_urls'] = df['url'].value_counts().head(10)

    # Методи
    results['methods'] = df['method'].value_counts()

    # Активність по часу
    results['hourly'] = df.resample('H', on='timestamp').size()

    # Середній розмір відповіді
    results['avg_size'] = df['size'].mean()

    # 🚨 Аномалії (IP з дуже великою кількістю запитів)
    threshold = df['ip'].value_counts().mean() * 3
    suspicious = df['ip'].value_counts()
    results['anomalies'] = suspicious[suspicious > threshold]

    return results

# ==========================================
# 4. STREAMLIT ІНТЕРФЕЙС
# ==========================================
st.set_page_config(page_title="Advanced Log Analyzer", layout="wide")
st.title("🛡️ Розширений аналізатор мережевих логів")

uploaded_file = st.sidebar.file_uploader("Завантаж лог-файл", type=["log", "txt"])

if uploaded_file:
    df = load_large_log(uploaded_file)

    if not df.empty:
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

        # 🚨 Аномалії
        st.subheader("🚨 Підозрілі IP")
        if not res['anomalies'].empty:
            st.warning("Виявлено потенційні аномалії!")
            st.bar_chart(res['anomalies'])
        else:
            st.success("Аномалій не виявлено")

        # Таблиця
        if st.checkbox("Показати дані"):
            st.dataframe(df.head(200), use_container_width=True)

    else:
        st.error("Файл не розпізнано")
else:
    st.info("Завантаж файл для аналізу")