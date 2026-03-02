import streamlit as st
import numpy as np
import faiss
import requests
import os
import re
import pickle
import json
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="AI RAG Pro", layout="wide")
st.title("🚀 AI RAG Pro (Streaming + Citations + Multi PDF)")

EMBEDDING_DIM = 384
INDEX_FILE = "faiss_index.bin"
META_FILE = "metadata.pkl"

# -----------------------------
# LOAD EMBEDDING MODEL
# -----------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -----------------------------
# SESSION INIT
# -----------------------------
if "index" not in st.session_state:
    if os.path.exists(INDEX_FILE):
        st.session_state.index = faiss.read_index(INDEX_FILE)
    else:
        st.session_state.index = faiss.IndexFlatIP(EMBEDDING_DIM)

if "metadata" not in st.session_state:
    if os.path.exists(META_FILE):
        with open(META_FILE, "rb") as f:
            st.session_state.metadata = pickle.load(f)
    else:
        st.session_state.metadata = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -----------------------------
# CHUNKING
# -----------------------------
def create_chunks(text, chunk_size=900, overlap=120):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# -----------------------------
# HIGHLIGHT
# -----------------------------
def highlight(text, query):
    words = query.split()
    for w in words:
        text = re.sub(f"(?i)({w})", r"<mark>\1</mark>", text)
    return text

# -----------------------------
# PDF UPLOAD
# -----------------------------
uploaded_files = st.file_uploader(
    "Upload PDF(s)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:

    for uploaded_file in uploaded_files:

        reader = PdfReader(uploaded_file)
        text_content = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_content += extracted

        if not text_content.strip():
            continue

        chunks = create_chunks(text_content)

        embeddings = model.encode(
            chunks,
            batch_size=128,
            show_progress_bar=False
        )

        embeddings = normalize(embeddings).astype("float32")

        st.session_state.index.add(embeddings)

        for chunk in chunks:
            st.session_state.metadata.append({
                "file": uploaded_file.name,
                "text": chunk
            })

    faiss.write_index(st.session_state.index, INDEX_FILE)

    with open(META_FILE, "wb") as f:
        pickle.dump(st.session_state.metadata, f)

    st.success("PDF(s) indexed successfully")

# -----------------------------
# MODEL SELECTION
# -----------------------------
st.sidebar.subheader("⚙ Model Settings")

model_choice = st.sidebar.selectbox(
    "Choose Local Model",
    ["tinyllama", "mistral", "llama3"]
)

# -----------------------------
# SEARCH + STREAMING AI
# -----------------------------
st.divider()
st.subheader("🔎 Ask Question")

query = st.text_input("Enter your question")

if st.button("Ask AI") and query:

    if st.session_state.index.ntotal == 0:
        st.warning("No documents indexed yet.")
        st.stop()

    query_embedding = model.encode([query])
    query_embedding = normalize(query_embedding).astype("float32")

    D, I = st.session_state.index.search(query_embedding, 3)

    context_chunks = []
    for idx in I[0]:
        if idx < len(st.session_state.metadata):
            meta = st.session_state.metadata[idx]
            context_chunks.append(
                f"[Source: {meta['file']}]\n{meta['text']}"
            )

    context = "\n\n".join(context_chunks)

    prompt = f"""
You are an intelligent assistant.
Answer strictly using the provided context.
If answer is not found in context, say "Not found in document."

Context:
{context}

Question:
{query}

Answer:
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_choice,
            "prompt": prompt,
            "stream": True
        },
        stream=True
    )

    answer_container = st.empty()
    full_response = ""

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line.decode())
            if "response" in chunk:
                full_response += chunk["response"]
                answer_container.markdown(full_response)

    st.session_state.chat_history.append(("User", query))
    st.session_state.chat_history.append(("AI", full_response))

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

# -----------------------------
# RESET
# -----------------------------
st.sidebar.divider()

if st.sidebar.button("Clear All Data"):
    st.session_state.index = faiss.IndexFlatIP(EMBEDDING_DIM)
    st.session_state.metadata = []
    st.session_state.chat_history = []

    if os.path.exists(INDEX_FILE):
        os.remove(INDEX_FILE)

    if os.path.exists(META_FILE):
        os.remove(META_FILE)

    st.sidebar.success("System Reset Done")
