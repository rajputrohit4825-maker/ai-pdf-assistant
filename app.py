import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from datetime import datetime

# -----------------------------------
# PAGE CONFIG
# -----------------------------------
st.set_page_config(page_title="AI PDF Platform", layout="wide")
st.title("📄 AI PDF Platform (PostgreSQL + Vector Ready)")

# -----------------------------------
# DATABASE CONNECTION
# -----------------------------------
DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    st.success("Database Connected Successfully ✅")
except Exception as e:
    st.error(f"Database Connection Failed: {e}")

# -----------------------------------
# LOGIN SYSTEM
# -----------------------------------
if "username" not in st.session_state:
    st.session_state["username"] = ""

if not st.session_state["username"]:
    st.subheader("🔐 Login Required")
    username_input = st.text_input("Enter Username")

    if st.button("Login"):
        if username_input.strip():
            st.session_state["username"] = username_input.strip()
            st.rerun()
        else:
            st.error("Username cannot be empty")
    st.stop()

st.sidebar.success(f"Logged in as: {st.session_state['username']}")

# -----------------------------------
# LOAD EMBEDDING MODEL
# -----------------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -----------------------------------
# PDF UPLOAD & INDEXING
# -----------------------------------
st.subheader("📂 Upload PDF")
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
        st.success("PDF text extracted ✅")

        # 🔥 500-character chunking (guaranteed insert)
        sentences = [
            text_content[i:i+500]
            for i in range(0, len(text_content), 500)
        ]

        st.write(f"Chunks created: {len(sentences)}")

        if st.button("Index Document to Database"):

            inserted_count = 0

            with engine.begin() as conn:
                for sentence in sentences:
                    embedding = model.encode(sentence).tolist()
                    vector_str = "[" + ",".join(map(str, embedding)) + "]"

                    conn.execute(
                        text("""
                            INSERT INTO documents 
                            (username, content, embedding_vector, created_at)
                            VALUES 
                            (:username, :content, CAST(:embedding AS vector), :created_at)
                        """),
                        {
                            "username": st.session_state["username"],
                            "content": sentence,
                            "embedding": vector_str,
                            "created_at": datetime.utcnow()
                        }
                    )

                    inserted_count += 1

            st.success(f"Inserted {inserted_count} chunks successfully ✅")

# -----------------------------------
# SEARCH SECTION
# -----------------------------------
st.divider()
st.subheader("🔎 Ask a Question")

query = st.text_input("Enter your question")

if st.button("Search") and query:

    query_vector = model.encode(query).tolist()
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT content,
                       1 - (embedding_vector <=> CAST(:query_vector AS vector)) AS similarity
                FROM documents
                WHERE username = :username
                ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
                LIMIT 3;
            """),
            {
                "username": st.session_state["username"],
                "query_vector": vector_str
            }
        )

        matches = result.fetchall()

    if matches:
        st.success("Top Relevant Results:")
        for row in matches:
            st.write("•", row[0])
    else:
        st.warning("No relevant answer found.")

# -----------------------------------
# SIDEBAR STATS
# -----------------------------------
st.sidebar.divider()
st.sidebar.subheader("📊 Stats")

with engine.connect() as conn:
    count = conn.execute(
        text("SELECT COUNT(*) FROM documents WHERE username = :username"),
        {"username": st.session_state["username"]}
    ).scalar()

st.sidebar.write(f"Indexed Chunks: {count}")

# -----------------------------------
# LOGOUT
# -----------------------------------
if st.sidebar.button("Logout"):
    st.session_state["username"] = ""
    st.rerun()
