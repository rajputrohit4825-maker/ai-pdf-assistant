import streamlit as st
import bcrypt
import numpy as np
import json
import re
from sqlalchemy import create_engine, text
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

# ------------------------------------------------
# CONFIG
# ------------------------------------------------

st.set_page_config(page_title="AI PDF Stable Build", layout="wide")

DATABASE_URL = st.secrets["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

# ------------------------------------------------
# DATABASE SETUP
# ------------------------------------------------

with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT
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
# SESSION
# ------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ------------------------------------------------
# AUTH
# ------------------------------------------------

if not st.session_state.logged_in:

    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO users(email,password) VALUES(:e,:p)"),
                    {"e": email, "p": hashed}
                )
            st.success("Registered")
        except:
            st.error("User exists")

    if st.button("Login"):
        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT password FROM users WHERE email=:e"),
                {"e": email}
            ).fetchone()

        if user and bcrypt.checkpw(password.encode(), user[0].encode()):
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.rerun()
        else:
            st.error("Invalid credentials")

# ------------------------------------------------
# MAIN APP
# ------------------------------------------------

else:

    st.success(f"Logged in as {st.session_state.user_email}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # ---------------- UPLOAD ----------------

    st.header("Upload PDF")

    uploaded = st.file_uploader("Choose PDF", type="pdf")

    if uploaded:

        reader = PdfReader(uploaded)
        text_data = ""

        for page in reader.pages:
            text_data += page.extract_text() or ""

        st.write("Extracted length:", len(text_data))

        if len(text_data) < 100:
            st.error("No readable text detected.")
        else:

            chunks = [text_data[i:i+700] for i in range(0, len(text_data), 600)]

            if st.button("Index Now"):

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
                    st.success("Indexing finished")

                except Exception as err:
                    trans.rollback()
                    st.error(f"Insert error: {err}")

                finally:
                    conn.close()

    # ---------------- VERIFY DATA ----------------

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE user_email=:e"),
            {"e": st.session_state.user_email}
        ).scalar()

    st.write("Stored chunks:", count)

    # ---------------- SEARCH ----------------

    st.header("Search")

    query = st.text_input("Ask something")

    if st.button("Search"):

        if count == 0:
            st.error("No documents indexed yet.")
            st.stop()

        q_emb = model.encode([query])
        q_emb = normalize(q_emb)[0]

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT content, embedding FROM documents WHERE user_email=:e"),
                {"e": st.session_state.user_email}
            ).fetchall()

        scored = []

        for row in rows:
            emb = np.array(json.loads(row[1]))
            score = np.dot(q_emb, emb)
            scored.append((score, row[0]))

        scored = sorted(scored, reverse=True)[:3]

        for s in scored:
            st.write("Score:", round(s[0],3))
            st.write(s[1])
            st.write("---")
