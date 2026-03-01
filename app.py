import streamlit as st
import re
import bcrypt
import random
import smtplib
import threading
import numpy as np

from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

# ------------------------------------------------
# CONFIG
# ------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

st.markdown("""
<style>
body {background-color: #0e1117; color: white;}
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed);
    color: white; border-radius: 8px;
}
section[data-testid="stSidebar"] {
    background-color: #111827;
}
</style>
""", unsafe_allow_html=True)

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

# ------------------------------------------------
# LOAD EMBEDDING MODEL
# ------------------------------------------------

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ------------------------------------------------
# DATABASE TABLES
# ------------------------------------------------

with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        subscription_status TEXT DEFAULT 'free',
        created_at TIMESTAMP DEFAULT NOW()
    );
    """))

    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS documents(
        id SERIAL PRIMARY KEY,
        user_email TEXT,
        file_name TEXT,
        content TEXT,
        embedding FLOAT8[],
        created_at TIMESTAMP DEFAULT NOW()
    );
    """))

# ------------------------------------------------
# SESSION INIT
# ------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ------------------------------------------------
# VALIDATION
# ------------------------------------------------

def valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def valid_password(password):
    return len(password) >= 6

# ------------------------------------------------
# EMAIL OTP
# ------------------------------------------------

def send_otp(email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}\nValid for 10 minutes.")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)
        return True
    except:
        return False

# ------------------------------------------------
# AUTH SECTION
# ------------------------------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF SaaS Platform")

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])

    # LOGIN
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            with engine.connect() as conn:
                user = conn.execute(
                    text("SELECT password, role, subscription_status FROM users WHERE email=:e"),
                    {"e": email}
                ).fetchone()

            if user and bcrypt.checkpw(password.encode(), user[0].encode()):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.role = user[1]
                st.session_state.plan = user[2]
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER
    with tab2:
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Password", type="password", key="reg_pass")

        if st.button("Register"):
            if not valid_email(reg_email):
                st.error("Invalid email format")
            elif not valid_password(reg_pass):
                st.error("Password must be 6+ characters")
            else:
                hashed = bcrypt.hashpw(reg_pass.encode(), bcrypt.gensalt()).decode()
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO users(email,password) VALUES(:e,:p)"),
                            {"e": reg_email, "p": hashed}
                        )
                    st.success("Registration successful")
                except:
                    st.error("Email already exists")

    # FORGOT
    with tab3:
        forgot_email = st.text_input("Enter registered email")

        if st.button("Send OTP"):
            otp = str(random.randint(100000,999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = forgot_email
            st.session_state.expiry = datetime.utcnow()+timedelta(minutes=10)

            if send_otp(forgot_email, otp):
                st.success("OTP sent")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP")
            new_pass = st.text_input("New Password", type="password")

            if st.button("Reset Password"):
                if datetime.utcnow() > st.session_state.expiry:
                    st.error("OTP expired")
                elif entered == st.session_state.reset_otp:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE users SET password=:p WHERE email=:e"),
                            {"p": hashed, "e": st.session_state.reset_email}
                        )
                    st.success("Password reset successful")
                else:
                    st.error("Invalid OTP")

# ------------------------------------------------
# MAIN DASHBOARD
# ------------------------------------------------

else:

    st.sidebar.success(f"{st.session_state.user_email}")
    st.sidebar.write(f"Role: {st.session_state.role}")
    st.sidebar.write(f"Plan: {st.session_state.plan}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # FILE LIMIT
    with engine.connect() as conn:
        file_count = conn.execute(
            text("SELECT COUNT(DISTINCT file_name) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

    st.sidebar.metric("Your Files", file_count)

    if st.session_state.plan == "free" and file_count >= 3:
        st.warning("Free plan allows max 3 PDFs")
        allow_upload = False
    else:
        allow_upload = True

    # UPLOAD
    st.header("📄 Upload PDF")

    if allow_upload:
        uploaded_files = st.file_uploader(
            "Upload multiple PDFs",
            type="pdf",
            accept_multiple_files=True
        )

        if uploaded_files:
            for uploaded in uploaded_files:

                if uploaded.size > 5 * 1024 * 1024:
                    st.error(f"{uploaded.name} too large (5MB max)")
                    continue

                reader = PdfReader(uploaded)
                text_data = ""

                for page in reader.pages:
                    text_data += page.extract_text() or ""

                def create_chunks(text, size=700, overlap=100):
                    chunks = []
                    start = 0
                    while start < len(text):
                        end = start + size
                        chunks.append(text[start:end])
                        start += size - overlap
                    return chunks

                chunks = create_chunks(text_data)

                def background_index(chunks, file_name):
                    embeddings = model.encode(chunks, batch_size=32)
                    embeddings = normalize(embeddings)

                    with engine.begin() as conn:
                        for chunk, emb in zip(chunks, embeddings):
                            conn.execute(
                                text("""
                                INSERT INTO documents
                                (user_email,file_name,content,embedding)
                                VALUES(:u,:f,:c,:e)
                                """),
                                {
                                    "u": st.session_state.user_email,
                                    "f": file_name,
                                    "c": chunk,
                                    "e": emb.tolist()
                                }
                            )

                if st.button(f"Index {uploaded.name}"):
                    threading.Thread(
                        target=background_index,
                        args=(chunks, uploaded.name)
                    ).start()
                    st.success(f"Indexing started for {uploaded.name}")

    # DELETE
    st.header("🗑 Manage Files")

    with engine.connect() as conn:
        files = conn.execute(
            text("SELECT DISTINCT file_name FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).fetchall()

    file_list = [f[0] for f in files]

    if file_list:
        selected = st.selectbox("Your Uploaded Files", file_list)

        if st.button("Delete Selected File"):
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    DELETE FROM documents
                    WHERE user_email=:e AND file_name=:f
                    """),
                    {"e": st.session_state.user_email, "f": selected}
                )
            st.success("File deleted")
            st.rerun()
    else:
        st.info("No files uploaded yet.")
