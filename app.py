import streamlit as st
import os
import bcrypt
import numpy as np
import re
from datetime import datetime
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AI PDF Platform Pro", layout="wide")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------- MODELS ----------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="user")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    content = Column(Text)
    embedding = Column(Text)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    question = Column(Text)
    timestamp = Column(DateTime)

Base.metadata.create_all(engine)

# ---------------- SECURITY ----------------

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ---------------- MODEL CACHE ----------------

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------------- SESSION ----------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- AUTH ----------------

if not st.session_state.logged_in:

    st.title("🔐 Secure Login System")

    menu = st.radio("Select", ["Login", "Register"])

    username = st.text_input("Username")
    email = st.text_input("Email (for register)")
    password = st.text_input("Password", type="password")

    db = SessionLocal()

    if menu == "Register":
        if st.button("Register"):
            try:
                new_user = User(
                    username=username,
                    email=email,
                    password=hash_password(password),
                    role="admin" if username == "admin" else "user"
                )
                db.add(new_user)
                db.commit()
                st.success("Registered Successfully")
            except:
                st.error("Username or Email already exists")

    if menu == "Login":
        if st.button("Login"):
            user = db.query(User).filter(User.username == username).first()
            if user and verify_password(password, user.password):
                st.session_state.logged_in = True
                st.session_state.username = user.username
                st.session_state.role = user.role
                st.rerun()
            else:
                st.error("Invalid Credentials")

    db.close()

# ---------------- MAIN APP ----------------

if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")
    page = st.sidebar.selectbox("Navigate", ["Chat", "History", "Admin"])

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    db = SessionLocal()

    # ---------------- CHAT ----------------
    if page == "Chat":

        st.title("📄 Semantic PDF Chat Engine")

        uploaded_file = st.file_uploader("Upload PDF", type="pdf")

        if uploaded_file:

            reader = PdfReader(uploaded_file)
            text = ""

            for page_obj in reader.pages:
                extracted = page_obj.extract_text()
                if extracted:
                    text += extracted + "\n"

            sentences = re.split(r"[.\n।]", text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            st.info("Indexing document...")

            for chunk in sentences:
                vector = model.encode(chunk).tolist()
                db_chunk = DocumentChunk(
                    username=st.session_state.username,
                    content=chunk,
                    embedding=str(vector)
                )
                db.add(db_chunk)

            db.commit()
            st.success("Document Indexed Successfully")

        query = st.text_input("Ask your question")

        if query:

            query_embedding = model.encode(query)

            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.username == st.session_state.username
            ).all()

            scored = []

            for chunk in chunks:
                stored_vector = np.array(eval(chunk.embedding))
                score = np.dot(stored_vector, query_embedding)
                scored.append((score, chunk.content))

            scored.sort(reverse=True)

            answer = " ".join([s[1] for s in scored[:3]])

            st.success("Answer")
            st.write(answer)

            new_history = History(
                username=st.session_state.username,
                question=query,
                timestamp=datetime.now()
            )
            db.add(new_history)
            db.commit()

    # ---------------- HISTORY ----------------
    if page == "History":

        st.title("📜 Search History")

        records = db.query(History).filter(
            History.username == st.session_state.username
        ).order_by(History.id.desc()).all()

        for record in records:
            st.write(f"{record.timestamp} - {record.question}")

    # ---------------- ADMIN DASHBOARD ----------------
    if page == "Admin" and st.session_state.role == "admin":

        st.title("📊 Admin Dashboard")

        total_users = db.query(User).count()
        total_docs = db.query(DocumentChunk).count()
        total_queries = db.query(History).count()

        st.metric("Total Users", total_users)
        st.metric("Total Documents Indexed", total_docs)
        st.metric("Total Queries", total_queries)

    db.close()
