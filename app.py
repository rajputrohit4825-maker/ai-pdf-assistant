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

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(page_title="AI PDF SaaS Platform", layout="wide")

st.markdown("""
<style>
body { background-color:#0e1117; color:white; }
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed);
    color:white;
    border-radius:10px;
    padding:8px 16px;
}
section[data-testid="stSidebar"] { background:#111827; }
</style>
""", unsafe_allow_html=True)

DATABASE_URL = st.secrets["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# =====================================================
# DATABASE TABLES
# =====================================================

with engine.begin() as conn:

    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        subscription_status TEXT DEFAULT 'free',
        created_at TIMESTAMP DEFAULT NOW()
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

# =====================================================
# SESSION INIT
# =====================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =====================================================
# EMAIL OTP
# =====================================================

def send_otp_email(to_email, otp):
    try:
        msg = MIMEText(f"Your OTP: {otp}\nValid for 10 minutes.")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com",465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)
        return True
    except:
        return False

# =====================================================
# AUTH SECTION
# =====================================================

if not st.session_state.logged_in:

    st.title("🔐 AI PDF SaaS Platform")

    tab1, tab2, tab3 = st.tabs(["Login","Register","Forgot Password"])

    # LOGIN
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password",type="password")

        if st.button("Login"):
            with engine.connect() as conn:
                result = conn.execute(text("""
                SELECT password, role, subscription_status
                FROM users WHERE email=:e
                """),{"e":email}).fetchone()

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
        reg_email = st.text_input("Email",key="r1")
        reg_pass = st.text_input("Password",type="password",key="r2")

        if st.button("Register"):
            hashed = bcrypt.hashpw(reg_pass.encode(),bcrypt.gensalt()).decode()
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                    INSERT INTO users(email,password)
                    VALUES(:e,:p)
                    """),{"e":reg_email,"p":hashed})
                st.success("Registered successfully")
            except:
                st.error("Email already exists")

    # FORGOT PASSWORD
    with tab3:
        forgot_email = st.text_input("Enter email")

        if st.button("Send OTP"):
            otp = str(random.randint(100000,999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = forgot_email
            st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=10)

            if send_otp_email(forgot_email,otp):
                st.success("OTP sent")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP")
            new_pass = st.text_input("New Password",type="password")

            if st.button("Reset Password"):
                if datetime.utcnow() > st.session_state.otp_expiry:
                    st.error("OTP expired")
                elif entered == st.session_state.reset_otp:
                    hashed = bcrypt.hashpw(new_pass.encode(),bcrypt.gensalt()).decode()
                    with engine.begin() as conn:
                        conn.execute(text("""
                        UPDATE users SET password=:p WHERE email=:e
                        """),{"p":hashed,"e":st.session_state.reset_email})
                    st.success("Password reset successful")
                    del st.session_state.reset_otp
                else:
                    st.error("Invalid OTP")

# =====================================================
# MAIN APP AFTER LOGIN
# =====================================================

else:

    st.sidebar.success(f"Logged in as {st.session_state.user_email}")
    st.sidebar.write(f"Role: {st.session_state.role}")
    st.sidebar.write(f"Plan: {st.session_state.plan}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    if st.session_state.role == "admin":

        st.header("🛠 Admin Dashboard")

        with engine.connect() as conn:
            total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            total_docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()

        col1,col2 = st.columns(2)
        col1.metric("Total Users",total_users)
        col2.metric("Total Chunks",total_docs)

        with engine.connect() as conn:
            usage = conn.execute(text("""
            SELECT user_email, COUNT(DISTINCT file_name)
            FROM documents
            GROUP BY user_email
            """)).fetchall()

        if usage:
            emails = [u[0] for u in usage]
            counts = [u[1] for u in usage]
            fig = plt.figure()
            plt.bar(emails,counts)
            plt.xticks(rotation=45)
            plt.title("Files per User")
            st.pyplot(fig)

    # =====================================================
    # USER ANALYTICS
    # =====================================================

    with engine.connect() as conn:
        total_files = conn.execute(text("""
        SELECT COUNT(DISTINCT file_name)
        FROM documents WHERE user_email=:e
        """),{"e":st.session_state.user_email}).scalar()

    st.sidebar.metric("Your Files",total_files)

    # =====================================================
    # DELETE DOCUMENT
    # =====================================================

    with engine.connect() as conn:
        files = conn.execute(text("""
        SELECT DISTINCT file_name FROM documents
        WHERE user_email=:e
        """),{"e":st.session_state.user_email}).fetchall()

    file_list = [f[0] for f in files]

    if file_list:
        selected = st.sidebar.selectbox("Your Files",file_list)
        if st.sidebar.button("Delete File"):
            with engine.begin() as conn:
                conn.execute(text("""
                DELETE FROM documents
                WHERE user_email=:e AND file_name=:f
                """),{"e":st.session_state.user_email,"f":selected})
            st.sidebar.success("Deleted")
            st.rerun()

    # =====================================================
    # PDF UPLOAD + FREE PLAN LIMIT
    # =====================================================

    st.header("📄 Upload PDF")

    uploaded_file = st.file_uploader("Choose PDF",type="pdf")

    if uploaded_file:

        if st.session_state.plan == "free" and total_files >= 3:
            st.warning("Free plan limit reached (3 PDFs)")
            st.stop()

        reader = PdfReader(uploaded_file)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() or ""

        def chunk_text(text,size=700,overlap=100):
            chunks=[]
            start=0
            while start<len(text):
                chunks.append(text[start:start+size])
                start+=size-overlap
            return chunks

        chunks = chunk_text(text_content)

        def background_index():
            embeddings = model.encode(chunks,batch_size=32)
            with engine.begin() as conn:
                for chunk,emb in zip(chunks,embeddings):
                    conn.execute(text("""
                    INSERT INTO documents(user_email,file_name,content,embedding)
                    VALUES(:e,:f,:c,:emb)
                    """),{
                        "e":st.session_state.user_email,
                        "f":uploaded_file.name,
                        "c":chunk,
                        "emb":emb.tolist()
                    })

        if st.button("Index Document"):
            threading.Thread(target=background_index).start()
            st.success("Indexing started")

    # =====================================================
    # CHAT MEMORY DISPLAY
    # =====================================================

    st.subheader("💬 Conversation")

    for role,msg in st.session_state.chat_history:
        if role=="You":
            st.markdown(f"**🧑 You:** {msg}")
        else:
            st.markdown(f"**🤖 AI:** {msg}")

    # =====================================================
    # SEARCH
    # =====================================================

    st.header("🔎 Ask Question")

    query = st.text_input("Enter your question")

    def highlight(text,query):
        for word in query.split():
            text = re.sub(f"(?i)({word})",r"<mark>\1</mark>",text)
        return text

    if st.button("Search"):

        query_embedding = model.encode([query])[0]

        with engine.connect() as conn:
            results = conn.execute(text("""
            SELECT content FROM documents
            WHERE user_email=:e
            ORDER BY embedding <=> :emb
            LIMIT 3
            """),{
                "e":st.session_state.user_email,
                "emb":query_embedding.tolist()
            }).fetchall()

        if results:
            combined=""
            for r in results:
                highlighted = highlight(r[0],query)
                st.markdown(f"""
                <div style='padding:12px;border:1px solid #444;
                border-radius:10px;margin-bottom:10px'>
                {highlighted}
                </div>
                """,unsafe_allow_html=True)
                combined+=r[0]+"\n\n"

            st.session_state.chat_history.append(("You",query))
            st.session_state.chat_history.append(("AI",combined.strip()))
        else:
            st.warning("No relevant answer found")
            st.session_state.chat_history.append(("You",query))
            st.session_state.chat_history.append(("AI","No relevant answer found"))
