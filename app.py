import streamlit as st
import random
import smtplib
import bcrypt
import numpy as np
import re
import threading
import matplotlib.pyplot as plt

from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS Platform", layout="wide")

st.markdown("""
<style>
body {background-color:#0e1117;color:white;}
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed);
    color:white;border-radius:12px;padding:0.5em 1em;
}
section[data-testid="stSidebar"] {background-color:#111827;}
</style>
""", unsafe_allow_html=True)

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
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user',
            subscription_status TEXT DEFAULT 'free'
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
# EMAIL OTP
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

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "search_count" not in st.session_state:
    st.session_state.search_count = 0

# ---------------------------------------------------
# AUTH SECTION
# ---------------------------------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF SaaS Platform")

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])

    # LOGIN
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT password, role, subscription_status FROM users WHERE email=:e"),
                    {"e": email}
                ).fetchone()

            if result and bcrypt.checkpw(password.encode(), result[0].encode()):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.role = result[1]
                st.session_state.plan = result[2]
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER
    with tab2:
        reg_email = st.text_input("Email", key="register_email")
        reg_pass = st.text_input("Password", type="password", key="register_password")

        if st.button("Register"):

            if "@" not in reg_email:
                st.warning("Invalid email")
                st.stop()

            if len(reg_pass) < 6:
                st.warning("Password too short")
                st.stop()

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
    with tab3:
        forgot_email = st.text_input("Enter registered email", key="forgot_email")

        if st.button("Send OTP"):
            otp = str(random.randint(100000, 999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = forgot_email
            st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=10)

            if send_otp_email(forgot_email, otp):
                st.success("OTP sent")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP", key="otp_input")
            new_pass = st.text_input("New Password", type="password", key="new_password")

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
# MAIN APP
# ---------------------------------------------------

else:

    st.sidebar.success(f"Logged in as {st.session_state.user_email}")
    st.sidebar.write(f"Role: {st.session_state.role}")
    st.sidebar.write(f"Plan: {st.session_state.plan}")

    # PLAN UI
    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 Subscription")

    if st.session_state.plan == "pro":
        st.sidebar.success("🚀 PRO PLAN ACTIVE")
        st.sidebar.write("Unlimited PDFs")
    else:
        st.sidebar.info("Free Plan")
        st.sidebar.write("Limit: 3 PDFs")
        if st.sidebar.button("Upgrade to Pro"):
            st.sidebar.info("Payment integration coming soon")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ADMIN DASHBOARD
    if st.session_state.role == "admin":
        st.header("🛠 Admin Dashboard")

        with engine.connect() as conn:
            total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            total_chunks = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()

        col1, col2 = st.columns(2)
        col1.metric("Total Users", total_users)
        col2.metric("Total Chunks", total_chunks)

        with engine.connect() as conn:
            file_counts = conn.execute(text("""
                SELECT user_email, COUNT(DISTINCT file_name)
                FROM documents GROUP BY user_email
            """)).fetchall()

        if file_counts:
            emails = [row[0] for row in file_counts]
            counts = [row[1] for row in file_counts]
            fig = plt.figure()
            plt.bar(emails, counts)
            plt.xticks(rotation=45)
            st.pyplot(fig)

    # USER STATS
    with engine.connect() as conn:
        total_files = conn.execute(
            text("SELECT COUNT(DISTINCT file_name) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

    st.sidebar.metric("Your Files", total_files)

    # DELETE FILE
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

    # PDF UPLOAD
    st.header("📄 Upload PDF")
    uploaded_file = st.file_uploader("Choose PDF", type="pdf")

    if uploaded_file:

        if uploaded_file.size > 10_000_000:
            st.warning("Max 10MB allowed")
            st.stop()

        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", uploaded_file.name)

        if st.session_state.plan == "free" and total_files >= 3:
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

        def background_index():
            embeddings = model.encode(
                chunks,
                batch_size=64,
                show_progress_bar=False,
                normalize_embeddings=True
            )
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
                            "f": safe_name,
                            "c": chunk,
                            "emb": emb.tolist()
                        }
                    )

        if st.button("Index Document"):
            thread = threading.Thread(target=background_index)
            thread.start()
            st.success("Indexing started")

    # CHAT DISPLAY
    st.subheader("💬 Conversation")
    for role, msg in st.session_state.chat_history:
        if role == "User":
            st.markdown(f"**🧑 You:** {msg}")
        else:
            st.markdown(f"**🤖 AI:** {msg}")

    # SEARCH
    st.header("🔎 Ask Question")
    query = st.text_input("Enter your question", key="search_input")

    if st.button("Search"):

        if not query.strip():
            st.warning("Enter a question")
            st.stop()

        if len(query) > 500:
            st.warning("Query too long")
            st.stop()

        if st.session_state.plan == "free":
            if st.session_state.search_count >= 20:
                st.warning("Free plan: 20 searches limit reached")
                st.stop()

        st.session_state.search_count += 1

        st.session_state.chat_history.append(("User", query))

        query_embedding = model.encode([query], normalize_embeddings=True)[0]

        with engine.connect() as conn:
            results = conn.execute(
                text("""
                    SELECT content FROM documents
                    WHERE user_email=:e
                    ORDER BY embedding <=> :emb
                    LIMIT 5
                """),
                {"e": st.session_state.user_email,
                 "emb": query_embedding.tolist()}
            ).fetchall()

        def highlight(text, query):
            words = query.split()
            for w in words:
                text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
            return text

        if results:
            answer = results[0][0]
            st.session_state.chat_history.append(("AI", answer))

            for r in results:
                highlighted = highlight(r[0], query)
                st.markdown(f"""
                <div style='padding:12px;border:1px solid #444;
                border-radius:10px;margin-bottom:10px'>
                {highlighted}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.session_state.chat_history.append(("AI", "No relevant answer found"))
            st.warning("No relevant answer found")
