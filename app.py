import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="AI PDF Platform", layout="wide")

st.title("📄 AI PDF Platform (PostgreSQL + Vector Ready)")

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

# Connection Test
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    st.success("Database Connected Successfully ✅")
except Exception as e:
    st.error(f"Database Connection Failed: {e}")

# -----------------------------
# USER SESSION
# -----------------------------
if "username" not in st.session_state:
    st.session_state.username = "demo_user"

# -----------------------------
# LOAD EMBEDDING MODEL (cached)
# -----------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -----------------------------
# PDF UPLOAD
# -----------------------------
uploaded_file = st.file_uploader("Upload your PDF", type="pdf")

if uploaded_file:

    reader = PdfReader(uploaded_file)
    text_content = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_content += extracted

    if not text_content.strip():
        st.error("No readable text found in PDF ❌")
    else:
        st.success("PDF processed successfully ✅")

        # Split into chunks
        sentences = text_content.split(". ")
        sentences = [s.strip() for s in sentences if len(s.strip()) > 50]

        if st.button("Index Document to Database"):
            with engine.begin() as conn:
                for sentence in sentences:
                    embedding = model.encode(sentence).tolist()

                    conn.execute(
                        text("""
                            INSERT INTO documents (username, content, embedding_vector, created_at)
                            VALUES (:username, :content, :embedding, :created_at)
                        """),
                        {
                            "username": st.session_state.username,
                            "content": sentence,
                            "embedding": embedding,
                            "created_at": datetime.utcnow()
                        }
                    )

            st.success("Document Indexed in PostgreSQL ✅")

# -----------------------------
# SEARCH SECTION
# -----------------------------
st.divider()
st.subheader("🔎 Ask a Question")

query = st.text_input("Enter your question")

if st.button("Search") and query:

    query_vector = model.encode(query).tolist()

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT content
                FROM documents
                WHERE username = :username
                ORDER BY embedding_vector <-> :query_vector
                LIMIT 3
            """),
            {
                "username": st.session_state.username,
                "query_vector": query_vector
            }
        )

        matches = result.fetchall()

    if matches:
        st.success("Top Relevant Results:")
        for row in matches:
            st.write("•", row[0])
    else:
        st.warning("No relevant answer found.")
