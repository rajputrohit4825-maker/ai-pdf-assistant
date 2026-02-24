import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import bcrypt
import jwt
import random
import smtplib

# ---------------------------
# CONFIG
# ---------------------------
SECRET_KEY = "supersecretkey123"
DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

st.set_page_config(layout="wide")
st.title("🚀 AI PDF Platform Enterprise")

# ---------------------------
# HELPERS
# ---------------------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(username, role):
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None

# ---------------------------
# SESSION INIT
# ---------------------------
if "token" not in st.session_state:
    st.session_state.token = None

# ---------------------------
# AUTH SECTION
# ---------------------------
def register():
    st.subheader("Register")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Create Account"):
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO users (username, email, password_hash)
                    VALUES (:username, :email, :password)
                """),
                {
                    "username": username,
                    "email": email,
                    "password": hash_password(password)
                }
            )
        st.success("Account created")

def login():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT password_hash, role FROM users WHERE username=:u"),
                {"u": username}
            ).fetchone()

        if result and verify_password(password, result[0]):
            token = create_token(username, result[1])
            st.session_state.token = token
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

def forgot_password():
    st.subheader("Forgot Password")
    email = st.text_input("Enter Email")

    if st.button("Send OTP"):
        otp = str(random.randint(100000, 999999))
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO password_resets (email, otp)
                    VALUES (:email, :otp)
                """),
                {"email": email, "otp": otp}
            )
        st.success(f"OTP Generated: {otp}")  # demo mode

    entered_otp = st.text_input("Enter OTP")
    new_pass = st.text_input("New Password", type="password")

    if st.button("Reset Password"):
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    SELECT otp FROM password_resets
                    WHERE email=:email
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"email": email}
            ).fetchone()

            if result and result[0] == entered_otp:
                conn.execute(
                    text("""
                        UPDATE users
                        SET password_hash=:password
                        WHERE email=:email
                    """),
                    {
                        "email": email,
                        "password": hash_password(new_pass)
                    }
                )
                st.success("Password updated")
            else:
                st.error("Invalid OTP")

# ---------------------------
# ROUTING
# ---------------------------
if not st.session_state.token:
    menu = st.radio("Select Option", ["Login", "Register", "Forgot Password"])
    if menu == "Login":
        login()
    elif menu == "Register":
        register()
    else:
        forgot_password()
    st.stop()

# ---------------------------
# TOKEN DECODE
# ---------------------------
user_data = decode_token(st.session_state.token)

if not user_data:
    st.session_state.token = None
    st.error("Session expired")
    st.stop()

username = user_data["username"]
role = user_data["role"]

st.sidebar.success(f"Logged in: {username} ({role})")

if st.sidebar.button("Logout"):
    st.session_state.token = None
    st.rerun()

# ---------------------------
# LOAD MODEL
# ---------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------------------
# PDF SECTION
# ---------------------------
st.subheader("Upload PDF")
file = st.file_uploader("Upload", type="pdf")

if file:
    reader = PdfReader(file)
    text_content = ""

    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_content += t

    chunks = [text_content[i:i+500] for i in range(0, len(text_content), 500)]

    if st.button("Index"):
        with engine.begin() as conn:
            for chunk in chunks:
                emb = model.encode(chunk).tolist()
                vector_str = "[" + ",".join(map(str, emb)) + "]"

                conn.execute(
                    text("""
                        INSERT INTO documents
                        (username, content, embedding_vector)
                        VALUES (:u, :c, CAST(:e AS vector))
                    """),
                    {"u": username, "c": chunk, "e": vector_str}
                )

        st.success("Indexed")

# ---------------------------
# SEARCH
# ---------------------------
st.subheader("Search")
query = st.text_input("Ask question")

if st.button("Search") and query:
    emb = model.encode(query).tolist()
    vector_str = "[" + ",".join(map(str, emb)) + "]"

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT content
                FROM documents
                WHERE username=:u
                ORDER BY embedding_vector <=> CAST(:q AS vector)
                LIMIT 3
            """),
            {"u": username, "q": vector_str}
        ).fetchall()

    for r in rows:
        st.write("•", r[0])

# ---------------------------
# ADMIN PANEL
# ---------------------------
if role == "admin":
    st.divider()
    st.subheader("Admin Panel")

    with engine.connect() as conn:
        total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        total_docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()

    st.write("Total Users:", total_users)
    st.write("Total Documents:", total_docs)

# ---------------------------
# ANALYTICS
# ---------------------------
st.sidebar.divider()
with engine.connect() as conn:
    user_docs = conn.execute(
        text("SELECT COUNT(*) FROM documents WHERE username=:u"),
        {"u": username}
    ).scalar()

st.sidebar.write("Your Indexed Docs:", user_docs)
