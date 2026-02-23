import streamlit as st
import sqlite3
import bcrypt
import secrets
from datetime import datetime, timedelta
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re
import pandas as pd

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="AI PDF Secure Platform", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password BLOB
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS password_resets (
    email TEXT,
    token TEXT,
    expiry TEXT
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

# ---------------- PASSWORD FUNCTIONS ----------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- AUTH SYSTEM ----------------
def register_user(username, email, password):
    try:
        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute("SELECT password FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    if user and check_password(password, user[0]):
        return True
    return False

# ---------------- LOGIN PAGE ----------------
if not st.session_state.logged_in:

    st.title("🔐 Secure Login System (Phase 1)")

    menu = st.radio("Select Option", ["Login", "Register", "Forgot Password"])

    if menu == "Register":
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Register"):
            if register_user(username, email, password):
                st.success("Account Created Successfully")
            else:
                st.error("Username or Email already exists")

    if menu == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid Credentials")

    if menu == "Forgot Password":
        email = st.text_input("Enter Registered Email")

        if st.button("Generate Reset Token"):
            token = secrets.token_hex(16)
            expiry = datetime.now() + timedelta(minutes=10)

            cursor.execute(
                "INSERT INTO password_resets VALUES (?, ?, ?)",
                (email, token, str(expiry))
            )
            conn.commit()

            st.success(f"Reset Token (valid 10 min): {token}")

        token_input = st.text_input("Enter Reset Token")
        new_password = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            cursor.execute(
                "SELECT expiry FROM password_resets WHERE token=?",
                (token_input,)
            )
            record = cursor.fetchone()

            if record:
                if datetime.now() < datetime.fromisoformat(record[0]):
                    hashed = hash_password(new_password)
                    cursor.execute(
                        "UPDATE users SET password=? WHERE email=(SELECT email FROM password_resets WHERE token=?)",
                        (hashed, token_input)
                    )
                    conn.commit()
                    st.success("Password Reset Successful")
                else:
                    st.error("Token Expired")
            else:
                st.error("Invalid Token")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📄 AI PDF Secure Intelligence Platform")

    # Cache Model
    @st.cache_resource
    def load_model():
        return SentenceTransformer("all-MiniLM-L6-v2")

    model = load_model()

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:

        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        sentences = re.split(r"[.\n।]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        embeddings = model.encode(sentences)

        query = st.text_input("Ask your question")

        if query:

            query_embedding = model.encode([query])
            similarities = np.dot(embeddings, query_embedding.T).flatten()
            top_indices = similarities.argsort()[-3:][::-1]

            answer = " ".join([sentences[i] for i in top_indices])

            st.success("Answer:")
            st.write(answer)

            cursor.execute(
                "INSERT INTO history (username, question, timestamp) VALUES (?, ?, ?)",
                (st.session_state.username, query, str(datetime.now()))
            )
            conn.commit()

    # ---------------- HISTORY ----------------
    st.divider()
    st.subheader("📜 Your Search History")

    cursor.execute(
        "SELECT question, timestamp FROM history WHERE username=? ORDER BY id DESC",
        (st.session_state.username,)
    )
    records = cursor.fetchall()

    for record in records:
        st.write(f"{record[1]} - {record[0]}")

    # ---------------- ANALYTICS ----------------
    st.divider()
    st.subheader("📊 Basic Analytics")

    cursor.execute("SELECT COUNT(*) FROM history WHERE username=?",
                   (st.session_state.username,))
    total_queries = cursor.fetchone()[0]

    st.metric("Total Queries", total_queries)
