import streamlit as st
import random
import smtplib
import bcrypt
import numpy as np
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------------------------------------------
# DATABASE TABLES
# ---------------------------------------------------

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            plan TEXT DEFAULT 'free'
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            file_name TEXT,
            content TEXT,
            embedding vector(384),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """))

# ---------------------------------------------------
# EMAIL OTP FUNCTION
# ---------------------------------------------------

def send_otp_email(to_email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}\nValid for 10 minutes.")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)

        return True
    except:
        return False

# ---------------------------------------------------
# SESSION INIT
# ---------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------------------------------------------
# AUTH SECTION
# ---------------------------------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF Platform")

    tab1, tab2 = st.tabs(["Login", "Register"])

    # LOGIN
    with tab1:
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
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER
    with tab2:
        reg_email = st.text_input("Email", key="r1")
        reg_pass = st.text_input("Password", type="password", key="r2")

        if st.button("Register"):
            hashed = bcrypt.hashpw(reg_pass.encode(), bcrypt.gensalt()).decode()
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO users (email,password) VALUES (:e,:p)"),
                        {"e": reg_email, "p": hashed}
                    )
                st.success("Registered successfully")
            except:
                st.error("Email already exists")

    # FORGOT PASSWORD
    st.subheader("Forgot Password")
    forgot_email = st.text_input("Enter registered email")

    if st.button("Send OTP"):
        otp = str(random.randint(100000, 999999))
        st.session_state.reset_otp = otp
        st.session_state.reset_email = forgot_email
        st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        if send_otp_email(forgot_email, otp):
            st.success("OTP sent to email")

    if "reset_otp" in st.session_state:
        entered = st.text_input("Enter OTP")
        new_pass = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            if datetime.utcnow() > st.session_state.otp_expiry:
                st.error("OTP expired")
            elif entered == st.session_state.reset_otp:
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE users SET password=:p WHERE email=:e"),
                        {"p": hashed, "e": st.session_state.reset_email}
                    )
                st.success("Password reset successful")
                del st.session_state.reset_otp
            else:
                st.error("Invalid OTP")

# ---------------------------------------------------
# MAIN APP AFTER LOGIN
# ---------------------------------------------------

else:

    st.sidebar.success(f"Logged in as {st.session_state.user_email}")

    # LOGOUT
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ---------------------------------------------------
    # ANALYTICS
    # ---------------------------------------------------

    with engine.connect() as conn:
        total_files = conn.execute(
            text("SELECT COUNT(DISTINCT file_name) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

        total_chunks = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

    st.sidebar.subheader("📊 Analytics")
    st.sidebar.metric("Total Files", total_files)
    st.sidebar.metric("Total Chunks", total_chunks)

    # ---------------------------------------------------
    # DELETE FILE
    # ---------------------------------------------------

    with engine.connect() as conn:
        files = conn.execute(
            text("SELECT DISTINCT file_name FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).fetchall()

    file_list = [f[0] for f in files]

    if file_list:
        selected_file = st.sidebar.selectbox("Your Files", file_list)

        if st.sidebar.button("Delete Selected File"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM documents WHERE user_email=:e AND file_name=:f"),
                    {"e": st.session_state.user_email, "f": selected_file}
                )
            st.sidebar.success("File deleted")
            st.rerun()

    # ---------------------------------------------------
    # PDF UPLOAD
    # ---------------------------------------------------

    st.header("📄 Upload PDF")

    uploaded_file = st.file_uploader("Choose PDF", type="pdf")

    if uploaded_file:

        # FREE PLAN LIMIT (3 PDFs)
        if total_files >= 3:
            st.warning("Free plan allows only 3 PDFs")
            st.stop()

        reader = PdfReader(uploaded_file)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() or ""

        def create_chunks(text, size=700, overlap=100):
            chunks = []
            start = 0
            while start < len(text):
                end = start + size
                chunks.append(text[start:end])
                start += size - overlap
            return chunks

        chunks = create_chunks(text_content)

        if st.button("Index Document"):

            embeddings = model.encode(chunks, batch_size=32)

            with engine.begin() as conn:
                for chunk, emb in zip(chunks, embeddings):
                    conn.execute(
                        text("""
                            INSERT INTO documents 
                            (user_email,file_name,content,embedding)
                            VALUES (:e,:f,:c,:emb)
                        """),
                        {
                            "e": st.session_state.user_email,
                            "f": uploaded_file.name,
                            "c": chunk,
                            "emb": emb.tolist()
                        }
                    )

            st.success("Document Indexed Successfully")

    # ---------------------------------------------------
    # SEARCH
    # ---------------------------------------------------

    st.header("🔎 Ask Question")

    query = st.text_input("Enter your question")

    def highlight(text, query):
        words = query.split()
        for w in words:
            text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
        return text

    if st.button("Search"):

        query_embedding = model.encode([query])[0]

        with engine.connect() as conn:
            results = conn.execute(
                text("""
                    SELECT content FROM documents
                    WHERE user_email=:e
                    ORDER BY embedding <=> :emb
                    LIMIT 5
                """),
                {
                    "e": st.session_state.user_email,
                    "emb": query_embedding.tolist()
                }
            ).fetchall()

        if results:
            for r in results:
                highlighted = highlight(r[0], query)
                st.markdown(f"""
                <div style='padding:12px;border:1px solid #ddd;
                border-radius:10px;margin-bottom:10px'>
                {highlighted}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("No relevant answer found")
