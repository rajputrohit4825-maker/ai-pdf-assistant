import streamlit as st
import numpy as np
import requests
import re
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="AI RAG System", layout="wide")
st.title("📄 AI RAG Project (Local + Fast)")

# -----------------------------
# LOAD EMBEDDING MODEL
# -----------------------------
@st.cache_resource
def load_model():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model

model = load_model()

# -----------------------------
# SESSION STORAGE
# -----------------------------
if "chunks" not in st.session_state:
    st.session_state.chunks = []

if "embeddings" not in st.session_state:
    st.session_state.embeddings = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -----------------------------
# SMART CHUNKING
# -----------------------------
def create_chunks(text, chunk_size=800, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# -----------------------------
# HIGHLIGHT FUNCTION
# -----------------------------
def highlight(text, query):
    words = query.split()
    for w in words:
        text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
    return text

# -----------------------------
# PDF UPLOAD
# -----------------------------
uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:

    reader = PdfReader(uploaded_file)
    text_content = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_content += extracted

    if not text_content.strip():
        st.error("No readable text found in PDF.")
    else:
        st.success("PDF loaded successfully")

        chunks = create_chunks(text_content)
        embeddings = model.encode(chunks, batch_size=64)
        embeddings = normalize(embeddings)

        st.session_state.chunks = chunks
        st.session_state.embeddings = embeddings

        st.success(f"{len(chunks)} chunks created & embedded")

# -----------------------------
# SEARCH + AI ANSWER
# -----------------------------
st.divider()
st.subheader("🔎 Ask Question")

query = st.text_input("Enter your question")

if st.button("Ask AI") and query:

    if st.session_state.embeddings is None:
        st.warning("No document indexed yet.")
        st.stop()

    query_embedding = model.encode([query])
    query_embedding = normalize(query_embedding)

    similarities = np.dot(st.session_state.embeddings, query_embedding.T).flatten()
    top_indices = similarities.argsort()[-3:][::-1]

    context = "\n\n".join([st.session_state.chunks[i] for i in top_indices])

    # -----------------------------
    # OLLAMA CALL (TinyLlama)
    # -----------------------------
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "tinyllama",
            "prompt": f"""
Use the context below to answer clearly.

Context:
{context}

Question:
{query}

Answer clearly:
""",
            "stream": False
        }
    )

    if response.status_code == 200:
        answer = response.json()["response"]

        st.session_state.chat_history.append(("User", query))
        st.session_state.chat_history.append(("AI", answer))

    else:
        st.error("Ollama not responding.")

# -----------------------------
# CHAT DISPLAY
# -----------------------------
st.divider()
st.subheader("💬 Conversation")

for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**🧑 You:** {msg}")
    else:
        st.markdown(f"**🤖 AI:** {msg}")
