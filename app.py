import streamlit as st
import re
import bcrypt
import numpy as np
import requests
import json
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

# ------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

st.markdown("""
<style>
body {background-color:#0e1117;color:white;}
.stButton>button {
    background:linear-gradient(90deg,#2563eb,#7c3aed);
    color:white;border-radius:8px;
}
mark {background:#7c3aed;color:white;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# DATABASE CONNECTION FIXED
# ------------------------------------------------

DATABASE_URL = st.secrets["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

# ------------------------------------------------
# CREATE TABLES
# ------------------------------------------------

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
        embedding TEXT
    );
    """))

# ------------------------------------------------
# LOAD MODEL
# ------------------------------------------------

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ------------------------------------------------
# SESSION INIT
# ------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "query_count" not in st.session_state:
    st.session_state.query_count = 0

# ------------------------------------------------
# HELPERS
# ------------------------------------------------

def valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def valid_password(p):
    return len(p) >= 6

def highlight(text, query):
    for w in query.split():
        text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
    return text

# ------------------------------------------------
# AUTH
# ------------------------------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF SaaS")

    tab1, tab2 = st.tabs(["Login", "Register"])

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

    with tab2:
        reg_email = st.text_input("Email", key="reg")
        reg_pass = st.text_input("Password", type="password", key="regp")

        if st.button("Register"):
            if not valid_email(reg_email):
                st.error("Invalid email")
            elif not valid_password(reg_pass):
                st.error("Password min 6 chars")
            else:
                hashed = bcrypt.hashpw(reg_pass.encode(), bcrypt.gensalt()).decode()
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO users(email,password) VALUES(:e,:p)"),
                            {"e": reg_email, "p": hashed}
                        )
                    st.success("Registered successfully")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

# ------------------------------------------------
# MAIN APP
# ------------------------------------------------

else:

    st.sidebar.success(st.session_state.user_email)
    st.sidebar.write(f"Plan: {st.session_state.plan}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ---------------- PDF UPLOAD ----------------

    st.header("📄 Upload PDF")
    uploaded = st.file_uploader("Upload PDF", type="pdf")

    if uploaded:

        reader = PdfReader(uploaded)
        text_data = ""

        for page in reader.pages:
            text_data += page.extract_text() or ""

        st.write("Extracted text length:", len(text_data))

        if len(text_data) < 50:
            st.error("PDF text not detected (possibly scanned PDF)")
        else:

            chunks = [text_data[i:i+700] for i in range(0, len(text_data), 600)]

            if st.button("Index PDF"):

                embeddings = model.encode(chunks)
                embeddings = normalize(embeddings)

                conn = engine.connect()
                trans = conn.begin()

                try:
                    for c, e in zip(chunks, embeddings):
                        conn.execute(text("""
                        INSERT INTO documents(user_email,file_name,content,embedding)
                        VALUES(:u,:f,:c,:e)
                        """), {
                            "u": st.session_state.user_email,
                            "f": uploaded.name,
                            "c": c,
                            "e": json.dumps(e.tolist())
                        })

                    trans.commit()
                    st.success("Indexing complete")

                except Exception as err:
                    trans.rollback()
                    st.error(f"Insert failed: {err}")

                finally:
                    conn.close()

                with engine.connect() as conn:
                    count = conn.execute(
                        text("SELECT COUNT(*) FROM documents WHERE user_email=:e"),
                        {"e": st.session_state.user_email}
                    ).scalar()

                st.write("Total stored chunks:", count)

    # ---------------- SEARCH ----------------

    st.header("🔎 Ask Question")
    query = st.text_input("Enter your question")

    if st.button("Search"):

        if len(query) > 300:
            st.error("Query too long")
            st.stop()

        if st.session_state.query_count >= 20:
            st.warning("Daily limit reached")
            st.stop()

        st.session_state.query_count += 1

        q_emb = model.encode([query])
        q_emb = normalize(q_emb)[0]

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT content, embedding FROM documents WHERE user_email=:e"),
                {"e": st.session_state.user_email}
            ).fetchall()

        if not rows:
            st.warning("No documents indexed yet.")
            st.stop()

        scored = []

        for row in rows:
            content = row[0]
            emb = np.array(json.loads(row[1]))
            score = np.dot(q_emb, emb)
            scored.append((score, content))

        scored = sorted(scored, reverse=True)[:3]

        if scored and scored[0][0] > 0.15:

            context = "\n".join([s[1] for s in scored])

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "tinyllama",
                    "prompt": f"Answer only from context:\n{context}\nQuestion:{query}",
                    "stream": False
                }
            ).json()["response"]

            st.session_state.chat_history.append(("User", query))
            st.session_state.chat_history.append(("AI", response))

            st.markdown(highlight(response, query), unsafe_allow_html=True)

        else:
            st.warning("Relevant answer not found.")

    # ---------------- CHAT HISTORY ----------------

    st.subheader("💬 Conversation")

    for role, msg in st.session_state.chat_history:
        if role == "User":
            st.markdown(f"**🧑 {msg}**")
        else:
            st.markdown(f"**🤖 {msg}**")
