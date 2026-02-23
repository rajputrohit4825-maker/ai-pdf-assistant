import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AI Document Intelligence", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    question TEXT,
    answer TEXT,
    timestamp TEXT
)
""")

conn.commit()

# ---------------- HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- MODEL LOAD (FAST) ----------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------- AUTH ----------------
def register_user(username, password, role="user"):
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       (username, hash_password(password), role))
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?",
                   (username, hash_password(password)))
    return cursor.fetchone()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- LOGIN PAGE ----------------
if not st.session_state.logged_in:

    st.title("🔐 AI Platform Login")

    menu = st.radio("Select", ["Login", "Register"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if menu == "Register":
        if st.button("Register"):
            if register_user(username, password):
                st.success("Registered Successfully")
            else:
                st.error("Username exists")

    if menu == "Login":
        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.session_state.role = user[3]
                st.rerun()
            else:
                st.error("Invalid credentials")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"User: {st.session_state.username}")
    st.sidebar.write(f"Role: {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📄 AI Document Intelligence Platform")

    uploaded_files = st.file_uploader("Upload PDF(s)", type="pdf", accept_multiple_files=True)

    if uploaded_files:

        full_text = ""

        for file in uploaded_files:
            reader = PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"

        if not full_text.strip():
            st.error("No readable text found.")
            st.stop()

        sentences = re.split(r"[.\n।]", full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 25]

        if "embeddings" not in st.session_state:
            st.session_state.embeddings = model.encode(sentences)
            st.session_state.sentences = sentences

        st.subheader("💬 Ask Question")
        query = st.text_input("Type your question")

        if query:

            query_embedding = model.encode([query])
            similarities = cosine_similarity(query_embedding, st.session_state.embeddings)[0]
            top_indices = similarities.argsort()[-3:][::-1]

            context = " ".join([st.session_state.sentences[i] for i in top_indices])

            st.markdown("### 🤖 Answer")
            st.write(context)

            cursor.execute("INSERT INTO history (username, question, answer, timestamp) VALUES (?, ?, ?, ?)",
                           (st.session_state.username, query, context, str(datetime.now())))
            conn.commit()

            st.download_button("Export Answer", context, "answer.txt")

    # ---------------- USER HISTORY ----------------
    st.divider()
    st.subheader("📜 Your History")

    df = pd.read_sql_query(
        f"SELECT question, timestamp FROM history WHERE username='{st.session_state.username}' ORDER BY id DESC",
        conn
    )

    if not df.empty:
        st.dataframe(df)

    # ---------------- ANALYTICS ----------------
    st.divider()
    st.subheader("📊 Analytics")

    total_queries = df.shape[0]
    st.metric("Total Queries", total_queries)

    if total_queries > 0:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
        chart = df.groupby("date").size()
        st.line_chart(chart)

    # ---------------- ADMIN DASHBOARD ----------------
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("🛠 Admin Dashboard")

        total_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn)
        total_history = pd.read_sql_query("SELECT COUNT(*) as count FROM history", conn)

        st.metric("Total Users", total_users["count"][0])
        st.metric("Total Queries (All Users)", total_history["count"][0])
