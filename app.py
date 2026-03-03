import streamlit as st
import random
import smtplib
import bcrypt
import re
import threading
import matplotlib.pyplot as plt
import numpy as np

from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

st.markdown("""
<style>
body {background-color:#0e1117;color:white;}
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed);
    color:white;border-radius:10px;
}
section[data-testid="stSidebar"] {background:#111827;}
mark {background-color:#facc15;color:black;padding:2px;border-radius:4px;}
</style>
""", unsafe_allow_html=True)

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------------------------------------------
# DB TABLES
# ---------------------------------------------------

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user',
            subscription_status TEXT DEFAULT 'free'
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents(
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            file_name TEXT,
            content TEXT,
            embedding vector(384),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """))

# ---------------------------------------------------
# EMAIL
# ---------------------------------------------------

def send_otp_email(to_email, otp):
    try:
        msg = MIMEText(f"Your OTP is {otp}. Valid for 10 minutes.")
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

if "search_timestamps" not in st.session_state:
    st.session_state.search_timestamps = []

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

        if st.button("Login", key="login_btn"):

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
        r_email = st.text_input("Email", key="reg_email")
        r_pass = st.text_input("Password", type="password", key="reg_pass")

        if st.button("Register", key="reg_btn"):

            if not r_pass or len(r_pass) < 6:
                st.warning("Password must be at least 6 characters")
                st.stop()

            hashed = bcrypt.hashpw(r_pass.encode(), bcrypt.gensalt()).decode()

            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO users(email,password) VALUES(:e,:p)"),
                        {"e": r_email, "p": hashed}
                    )
                st.success("Registered successfully")
            except:
                st.error("Email already exists")

    # FORGOT PASSWORD
    with tab3:
        f_email = st.text_input("Enter registered email", key="forgot_email")

        if st.button("Send OTP", key="otp_btn"):
            otp = str(random.randint(100000, 999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = f_email
            st.session_state.expiry = datetime.utcnow() + timedelta(minutes=10)

            if send_otp_email(f_email, otp):
                st.success("OTP sent")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP", key="otp_input")
            new_pass = st.text_input("New Password", type="password", key="new_pass")

            if st.button("Reset Password", key="reset_btn"):

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

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ADMIN DASHBOARD
    if st.session_state.role == "admin":
        st.header("🛠 Admin Dashboard")

        with engine.connect() as conn:
            total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            total_docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()

        c1, c2 = st.columns(2)
        c1.metric("Total Users", total_users)
        c2.metric("Total Chunks", total_docs)

        st.subheader("Usage Chart")

        with engine.connect() as conn:
            data = conn.execute(text("""
                SELECT user_email, COUNT(*) FROM documents
                GROUP BY user_email
            """)).fetchall()

        if data:
            users = [d[0] for d in data]
            counts = [d[1] for d in data]
            fig = plt.figure()
            plt.bar(users, counts)
            plt.xticks(rotation=45)
            st.pyplot(fig)

    # USER ANALYTICS
    with engine.connect() as conn:
        total_files = conn.execute(
            text("SELECT COUNT(DISTINCT file_name) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

    st.sidebar.metric("Your PDFs", total_files)

    # FILE MANAGEMENT
    with engine.connect() as conn:
        files = conn.execute(
            text("SELECT DISTINCT file_name FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).fetchall()

    file_list = [f[0] for f in files]

    if file_list:
        selected = st.sidebar.selectbox("Your Files", file_list)

        if st.sidebar.button("Delete File"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM documents WHERE user_email=:e AND file_name=:f"),
                    {"e": st.session_state.user_email, "f": selected}
                )
            st.success("Deleted")
            st.rerun()

    # UPLOAD
    st.header("📄 Upload PDF")

    uploaded = st.file_uploader("Choose PDF", type="pdf")

    if uploaded:

        if uploaded.size > 10_000_000:
            st.warning("Maximum file size is 10MB")
            st.stop()

        if st.session_state.plan == "free" and total_files >= 3:
            st.warning("Free plan limit reached")
            st.stop()

        reader = PdfReader(uploaded)
        text_data = "".join(page.extract_text() or "" for page in reader.pages)

        def chunk_text(text, size=700, overlap=100):
            chunks = []
            i = 0
            while i < len(text):
                chunks.append(text[i:i+size])
                i += size - overlap
            return chunks

        chunks = chunk_text(text_data)

        def index_bg():
            embeddings = model.encode(chunks, batch_size=32)
            with engine.begin() as conn:
                for chunk, emb in zip(chunks, embeddings):
                    conn.execute(
                        text("""
                            INSERT INTO documents(user_email,file_name,content,embedding)
                            VALUES(:e,:f,:c,:emb)
                        """),
                        {
                            "e": st.session_state.user_email,
                            "f": uploaded.name,
                            "c": chunk,
                            "emb": emb.tolist()
                        }
                    )

        if st.button("Index Document"):
            threading.Thread(target=index_bg).start()
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

    query = st.text_input("Enter question", key="query_input")

    if st.button("Search", key="search_btn"):

        if not query or not query.strip():
            st.warning("Enter a valid question")
            st.stop()

        now = datetime.utcnow()
        st.session_state.search_timestamps = [
            t for t in st.session_state.search_timestamps
            if (now - t).total_seconds() < 60
        ]

        if len(st.session_state.search_timestamps) >= 5:
            st.warning("Too many searches. Please wait.")
            st.stop()

        st.session_state.search_timestamps.append(now)

        st.session_state.chat_history.append(("User", query))

        q_emb = model.encode([query])[0]

        with engine.connect() as conn:
            results = conn.execute(
                text("""
                    SELECT content FROM documents
                    WHERE user_email=:e
                    ORDER BY embedding <=> :emb
                    LIMIT 3
                """),
                {
                    "e": st.session_state.user_email,
                    "emb": q_emb.tolist()
                }
            ).fetchall()

        def highlight(text):
            for w in query.split():
                text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
            return text

        if results:
            answer = results[0][0]
            st.session_state.chat_history.append(("AI", answer))
            for r in results:
                st.markdown(highlight(r[0]), unsafe_allow_html=True)
        else:
            st.session_state.chat_history.append(("AI", "No relevant answer found"))
            st.warning("No relevant answer found")
