import streamlit as st
import random
import smtplib
import bcrypt
import stripe
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader

# -------------------------
# CONFIG
# -------------------------

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

# -------------------------
# EMAIL FUNCTION
# -------------------------

def send_otp_email(to_email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Password Reset OTP"
    msg["From"] = st.secrets["EMAIL_ADDRESS"]
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(
            st.secrets["EMAIL_ADDRESS"],
            st.secrets["EMAIL_PASSWORD"]
        )
        server.send_message(msg)

# -------------------------
# CREATE TABLES
# -------------------------

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            plan TEXT DEFAULT 'free'
        )
    """))

    conn.execute(text("""
        CREATE EXTENSION IF NOT EXISTS vector;
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            content TEXT,
            embedding_vector VECTOR(384),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))

# -------------------------
# SESSION INIT
# -------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------------
# AUTH SECTION
# -------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF Platform")

    menu = st.radio("Select Option", ["Login", "Register", "Forgot Password"])

    # REGISTER
    if menu == "Register":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Register"):
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO users (email, password) VALUES (:e, :p)"),
                        {"e": email, "p": hashed}
                    )
                st.success("Registration successful")
            except:
                st.error("Email already exists")

    # LOGIN
    if menu == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT password FROM users WHERE email=:e"),
                    {"e": email}
                ).fetchone()

            if result and bcrypt.checkpw(password.encode(), result[0].encode()):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # FORGOT PASSWORD
    if menu == "Forgot Password":
        email = st.text_input("Enter your email")

        if st.button("Send OTP"):
            otp = str(random.randint(100000, 999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = email
            st.session_state.expiry = datetime.utcnow() + timedelta(minutes=10)
            send_otp_email(email, otp)
            st.success("OTP sent")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP")
            new_pass = st.text_input("New Password", type="password")

            if st.button("Reset Password"):
                if entered == st.session_state.reset_otp:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE users SET password=:p WHERE email=:e"),
                            {"p": hashed, "e": st.session_state.reset_email}
                        )
                    st.success("Password reset successful")
                else:
                    st.error("Invalid OTP")

    st.stop()

# -------------------------
# LOGGED IN DASHBOARD
# -------------------------

st.sidebar.success(f"Logged in as: {st.session_state.user_email}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.title("📄 AI PDF SaaS Dashboard")

# -------------------------
# LOAD MODEL
# -------------------------

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -------------------------
# PDF UPLOAD
# -------------------------

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    text_content = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_content += page_text

    chunks = [text_content[i:i+500] for i in range(0, len(text_content), 500)]

    if st.button("Index Document"):

        # Free plan limit
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM documents WHERE user_email=:e"),
                {"e": st.session_state.user_email}
            ).scalar()

        if count > 100:
            st.error("Free plan limit reached. Upgrade required.")
        else:
            with engine.begin() as conn:
                for chunk in chunks:
                    emb = model.encode(chunk).tolist()
                    vector_str = "[" + ",".join(map(str, emb)) + "]"

                    conn.execute(
                        text("""
                            INSERT INTO documents
                            (user_email, content, embedding_vector)
                            VALUES (:e, :c, CAST(:v AS vector))
                        """),
                        {"e": st.session_state.user_email,
                         "c": chunk,
                         "v": vector_str}
                    )

            st.success("Document Indexed")

# -------------------------
# SEARCH
# -------------------------

query = st.text_input("Ask Question")

if st.button("Search") and query:

    emb = model.encode(query).tolist()
    vector_str = "[" + ",".join(map(str, emb)) + "]"

    with engine.connect() as conn:
        results = conn.execute(
            text("""
                SELECT content
                FROM documents
                WHERE user_email=:e
                ORDER BY embedding_vector <=> CAST(:v AS vector)
                LIMIT 3
            """),
            {"e": st.session_state.user_email,
             "v": vector_str}
        ).fetchall()

    for row in results:
        st.write("•", row[0])
