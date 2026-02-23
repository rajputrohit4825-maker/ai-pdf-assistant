import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="AI PDF Platform", layout="wide")

# ---------------- DATABASE SETUP ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
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

# ---------------- PASSWORD HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- AUTH SYSTEM ----------------
def register_user(username, password):
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                       (username, hash_password(password)))
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

    st.title("🔐 Login System")

    menu = st.radio("Select", ["Login", "Register"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if menu == "Register":
        if st.button("Register"):
            if register_user(username, password):
                st.success("Registered Successfully")
            else:
                st.error("Username already exists")

    if menu == "Login":
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login Successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📄 AI PDF Intelligence Platform")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:

        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        if not text.strip():
            st.error("No readable text found.")
            st.stop()

        sentences = re.split(r"[.\n।]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(sentences)

        st.subheader("💬 Ask Question")
        query = st.text_input("Type your question")

        if query:

            query_embedding = model.encode([query])
            similarities = np.dot(embeddings, query_embedding.T).flatten()
            top_indices = similarities.argsort()[-3:][::-1]

            context = " ".join([sentences[i] for i in top_indices])
            answer = context

            st.success("Answer:")
            st.write(answer)

            # Save history
            cursor.execute("INSERT INTO history (username, question, answer, timestamp) VALUES (?, ?, ?, ?)",
                           (st.session_state.username, query, answer, str(datetime.now())))
            conn.commit()

    # ---------------- HISTORY ----------------
    st.divider()
    st.subheader("📜 Your Search History")

    cursor.execute("SELECT question, timestamp FROM history WHERE username=? ORDER BY id DESC",
                   (st.session_state.username,))
    records = cursor.fetchall()

    for record in records:
        st.write(f"🕒 {record[1]} - {record[0]}")

    # ---------------- ANALYTICS ----------------
    st.divider()
    st.subheader("📊 Analytics Dashboard")

    cursor.execute("SELECT COUNT(*) FROM history WHERE username=?",
                   (st.session_state.username,))
    total_queries = cursor.fetchone()[0]

    st.metric("Total Queries", total_queries)
