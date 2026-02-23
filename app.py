import streamlit as st
import sqlite3
import json
import re
import threading
from datetime import datetime
from sentence_transformers import SentenceTransformer
import numpy as np
from PyPDF2 import PdfReader
from passlib.context import CryptContext

st.set_page_config(page_title="AI PDF Platform v3", layout="wide")

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
    embedding_vector TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_user ON documents(username)
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

# ---------------- ASYNC INDEXING ----------------
def index_document(username, sentences):
    for sentence in sentences:
        embedding = model.encode(sentence).tolist()

        cursor.execute("""
            INSERT INTO documents (username, content, embedding_vector, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            username,
            sentence,
            json.dumps(embedding),
            str(datetime.now())
        ))

    conn.commit()

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

    st.title("📄 AI PDF Platform – Phase 3 Vector Upgrade")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:

        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        sentences = re.split(r"[.\n।]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 40]

        st.info("Indexing in background...")

        threading.Thread(
            target=index_document,
            args=(st.session_state.username, sentences)
        ).start()

        st.success("Document indexing started (async)")

    st.divider()
    st.subheader("💬 Semantic Search")

    query = st.text_input("Ask your question")

    if query:

        query_embedding = model.encode(query)

        cursor.execute("""
            SELECT content, embedding_vector
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

        st.success("Best Match:")
        st.write(best_answer)
