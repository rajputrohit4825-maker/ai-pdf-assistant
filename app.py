import streamlit as st
import sqlite3
import json
import re
from datetime import datetime
from sentence_transformers import SentenceTransformer
import numpy as np
from PyPDF2 import PdfReader
from passlib.context import CryptContext

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="AI PDF Platform v2", layout="wide")

# ---------------- DATABASE ----------------
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
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    content TEXT,
    embedding TEXT,
    created_at TEXT
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

# ---------------- SECURITY ----------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

# ---------------- AUTH ----------------
def register_user(username, password):
    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute("SELECT password FROM users WHERE username=?", (username,))
    result = cursor.fetchone()
    if result and verify_password(password, result[0]):
        return True
    return False

# ---------------- MODEL CACHE ----------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- LOGIN ----------------
if not st.session_state.logged_in:

    st.title("🔐 Secure Login")

    menu = st.radio("Select", ["Login", "Register"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if menu == "Register":
        if st.button("Register"):
            if register_user(username, password):
                st.success("Account Created")
            else:
                st.error("Username exists")

    if menu == "Login":
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📄 AI PDF Platform – Phase 2 Database Upgrade")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:

        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        sentences = re.split(r"[.\n।]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        st.info("Indexing document...")

        for sentence in sentences:
            embedding = model.encode(sentence).tolist()

            cursor.execute("""
                INSERT INTO documents (username, content, embedding, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                st.session_state.username,
                sentence,
                json.dumps(embedding),
                str(datetime.now())
            ))

        conn.commit()
        st.success("Document Indexed Successfully")

    st.divider()
    st.subheader("💬 Ask Question")

    query = st.text_input("Enter your question")

    if query:

        query_embedding = model.encode(query)

        cursor.execute("""
            SELECT content, embedding
            FROM documents
            WHERE username=?
        """, (st.session_state.username,))

        records = cursor.fetchall()

        best_score = -1
        best_answer = ""

        for content, emb_text in records:
            embedding = np.array(json.loads(emb_text))
            score = np.dot(embedding, query_embedding)

            if score > best_score:
                best_score = score
                best_answer = content

        st.success("Best Answer:")
        st.write(best_answer)

        cursor.execute("""
            INSERT INTO history (username, question, timestamp)
            VALUES (?, ?, ?)
        """, (
            st.session_state.username,
            query,
            str(datetime.now())
        ))

        conn.commit()

    # ---------------- ANALYTICS ----------------
    st.divider()
    st.subheader("📊 Analytics")

    cursor.execute("SELECT COUNT(*) FROM documents WHERE username=?",
                   (st.session_state.username,))
    doc_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE username=?",
                   (st.session_state.username,))
    query_count = cursor.fetchone()[0]

    st.metric("Indexed Chunks", doc_count)
    st.metric("Total Queries", query_count)
