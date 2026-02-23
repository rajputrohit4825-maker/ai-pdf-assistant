import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re
import pandas as pd

st.set_page_config(page_title="AI PDF Intelligence Platform", layout="wide")

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
    timestamp TEXT
)
""")

conn.commit()

# ---------------- HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- AUTH ----------------
def register_user(username, password):
    try:
        role = "admin" if username == "admin" else "user"
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       (username, hash_password(password), role))
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?",
                   (username, hash_password(password)))
    return cursor.fetchone()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- LOGIN ----------------
if not st.session_state.logged_in:

    st.title("🔐 Secure Login System")

    menu = st.radio("Select Option", ["Login", "Register"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if menu == "Register":
        if st.button("Register"):
            if register_user(username, password):
                st.success("Account Created Successfully")
            else:
                st.error("Username already exists")

    if menu == "Login":
        if st.button("Login"):
            result = login_user(username, password)
            if result:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = result[0]
                st.rerun()
            else:
                st.error("Invalid Credentials")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    page = st.sidebar.selectbox("Navigate", ["Chat", "History", "Analytics"])

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ---------------- LOAD MODEL ONCE ----------------
    @st.cache_resource
    def load_model():
        return SentenceTransformer("all-MiniLM-L6-v2")

    model = load_model()

    # ---------------- CHAT PAGE ----------------
    if page == "Chat":

        st.title("📄 AI Semantic PDF Chat")

        uploaded_files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True)

        if uploaded_files:

            all_sentences = []

            for file in uploaded_files:
                reader = PdfReader(file)
                text = ""

                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"

                sentences = re.split(r"[.\n।]", text)
                sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
                all_sentences.extend(sentences)

            embeddings = model.encode(all_sentences)

            query = st.text_input("Ask your question")

            if query:

                query_embedding = model.encode([query])
                similarities = np.dot(embeddings, query_embedding.T).flatten()
                top_indices = similarities.argsort()[-3:][::-1]

                answer = " ".join([all_sentences[i] for i in top_indices])

                st.success("Answer:")
                st.write(answer)

                cursor.execute("INSERT INTO history (username, question, timestamp) VALUES (?, ?, ?)",
                               (st.session_state.username, query, str(datetime.now())))
                conn.commit()

    # ---------------- HISTORY PAGE ----------------
    if page == "History":

        st.title("📜 Search History")

        if st.session_state.role == "admin":
            cursor.execute("SELECT username, question, timestamp FROM history ORDER BY id DESC")
        else:
            cursor.execute("SELECT username, question, timestamp FROM history WHERE username=? ORDER BY id DESC",
                           (st.session_state.username,))

        data = cursor.fetchall()

        df = pd.DataFrame(data, columns=["User", "Question", "Time"])
        st.dataframe(df)

    # ---------------- ANALYTICS PAGE ----------------
    if page == "Analytics":

        st.title("📊 Analytics Dashboard")

        cursor.execute("SELECT COUNT(*) FROM history")
        total_queries = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        st.metric("Total Users", total_users)
        st.metric("Total Queries", total_queries)

        cursor.execute("SELECT username, COUNT(*) as count FROM history GROUP BY username")
        data = cursor.fetchall()

        if data:
            df = pd.DataFrame(data, columns=["User", "Queries"])
            st.bar_chart(df.set_index("User"))
