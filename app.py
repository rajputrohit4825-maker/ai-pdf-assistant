import streamlit as st
import numpy as np
import faiss
import requests
import os
import pickle
import json
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="AI RAG Fast Pro", layout="wide")

st.markdown("""
<style>
body { background-color:#0e1117; }
.stButton>button {
    border-radius:10px;
    background:linear-gradient(90deg,#2563eb,#7c3aed);
    color:white;
}
</style>
""", unsafe_allow_html=True)

st.title("🚀 AI RAG Fast Pro (CPU Optimized)")

EMBEDDING_DIM = 384
INDEX_FILE = "faiss_index.bin"
META_FILE = "metadata.pkl"

# =============================
# LOAD MODELS
# =============================
@st.cache_resource
def load_embed_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

@st.cache_resource
def load_reranker():
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

embed_model = load_embed_model()
reranker = load_reranker()

# =============================
# SESSION INIT
# =============================
if "index" not in st.session_state:
    if os.path.exists(INDEX_FILE):
        st.session_state.index = faiss.read_index(INDEX_FILE)
    else:
        index = faiss.IndexHNSWFlat(EMBEDDING_DIM, 32)
        index.hnsw.efSearch = 50
        index.hnsw.efConstruction = 40
        st.session_state.index = index

if "metadata" not in st.session_state:
    if os.path.exists(META_FILE):
        with open(META_FILE, "rb") as f:
            st.session_state.metadata = pickle.load(f)
    else:
        st.session_state.metadata = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =============================
# CACHE EMBEDDING
# =============================
@st.cache_data(show_spinner=False)
def cached_embedding(text):
    return embed_model.encode(
        [text],
        convert_to_numpy=True,
        normalize_embeddings=True
    )[0]

# =============================
# QUERY EXPANSION
# =============================
def expand_query(q, model):
    prompt = f"Rewrite this question to improve retrieval:\n\n{q}\n\nImproved:"
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        return r.json().get("response", q).strip()
    except:
        return q

# =============================
# CHUNKING
# =============================
def create_chunks(text, size=900, overlap=120):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

# =============================
# PDF UPLOAD
# =============================
uploaded_files = st.file_uploader(
    "Upload PDF(s)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        reader = PdfReader(file)
        text_content = ""

        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_content += t

        if not text_content.strip():
            continue

        chunks = create_chunks(text_content)

        embeddings = embed_model.encode(
            chunks,
            batch_size=256,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")

        st.session_state.index.add(embeddings)

        for i, chunk in enumerate(chunks):
            st.session_state.metadata.append({
                "file": file.name,
                "page": i+1,
                "text": chunk
            })

    faiss.write_index(st.session_state.index, INDEX_FILE)
    with open(META_FILE, "wb") as f:
        pickle.dump(st.session_state.metadata, f)

    st.success("Documents Indexed Successfully")

# =============================
# AUTO SUMMARY
# =============================
if st.button("📄 Generate Document Summary"):
    if not st.session_state.metadata:
        st.warning("No documents available.")
    else:
        full_text = "\n".join(
            [m["text"] for m in st.session_state.metadata[:20]]
        )
        prompt = f"Summarize clearly:\n\n{full_text}\n\nSummary:"
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model":"tinyllama","prompt":prompt,"stream":False}
        )
        summary = r.json().get("response","")
        st.subheader("Document Summary")
        st.write(summary)

# =============================
# SETTINGS
# =============================
st.sidebar.subheader("⚙ Settings")
model_choice = st.sidebar.selectbox(
    "Choose Model",
    ["tinyllama","mistral","llama3"]
)

fast_mode = st.sidebar.toggle("⚡ Fast Mode (Skip Re-Rank)")
reasoning_mode = st.sidebar.toggle("🧠 Advanced Reasoning")

# =============================
# DOCUMENT FILTER
# =============================
file_list = list(set([m["file"] for m in st.session_state.metadata]))
selected_file = st.selectbox(
    "Filter by Document",
    ["All Documents"] + file_list
)

# =============================
# ASK QUESTION
# =============================
st.divider()
st.subheader("🔎 Ask Question")

query = st.text_input("Enter your question")

if st.button("Ask AI") and query:

    if st.session_state.index.ntotal == 0:
        st.warning("No documents indexed yet.")
        st.stop()

    expanded_query = expand_query(query, model_choice)
    st.info(f"Expanded Query: {expanded_query}")

    history_text = ""
    for role,msg in st.session_state.chat_history[-4:]:
        history_text += f"{role}: {msg}\n"

    enhanced_query = history_text + expanded_query

    q_vector = cached_embedding(enhanced_query)
    q_embed = np.array([q_vector]).astype("float32")

    D,I = st.session_state.index.search(q_embed,5)

    scored = []

    for pos, idx in enumerate(I[0]):
        if idx < len(st.session_state.metadata):
            meta = st.session_state.metadata[idx]

            if selected_file != "All Documents":
                if meta["file"] != selected_file:
                    continue

            keyword_score = sum(
                1 for w in expanded_query.lower().split()
                if w in meta["text"].lower()
            )

            vector_score = float(D[0][pos])
            final_score = vector_score + (0.1*keyword_score)

            scored.append((final_score, meta))

    scored.sort(key=lambda x:x[0], reverse=True)
    top_candidates = scored[:3]

    if fast_mode:
        top_results = top_candidates
        confidence = round(float(top_results[0][0])*100,2)
    else:
        pairs = [(expanded_query, m["text"]) for _,m in top_candidates]
        rerank_scores = reranker.predict(pairs)

        reranked = []
        for i,score in enumerate(rerank_scores):
            reranked.append((score, top_candidates[i][1]))

        reranked.sort(key=lambda x:x[0], reverse=True)
        top_results = reranked
        confidence = round(float(reranked[0][0])*100,2)

    context_parts = []
    for score,meta in top_results:
        st.caption(f"Score: {round(score,3)} | {meta['file']} | Page {meta['page']}")
        context_parts.append(
            f"[Source: {meta['file']} | Page {meta['page']}]\n{meta['text']}"
        )

    context = "\n\n".join(context_parts)

    if reasoning_mode:
        prompt = f"""
Think step by step internally.
Answer clearly using only context.

Context:
{context}

Question:
{query}

Final Answer:
"""
    else:
        prompt = f"""
Answer using only context.
If not found say: Not found in document.

Context:
{context}

Question:
{query}

Answer:
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model":model_choice,"prompt":prompt,"stream":True},
        stream=True
    )

    container = st.empty()
    final_answer = ""

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line.decode())
            if "response" in chunk:
                final_answer += chunk["response"]
                container.markdown(final_answer)

    st.divider()
    st.subheader("📊 Confidence Score")

    if confidence > 70:
        st.success(f"High Confidence: {confidence}%")
    elif confidence > 40:
        st.warning(f"Medium Confidence: {confidence}%")
    else:
        st.error(f"Low Confidence: {confidence}%")

    st.session_state.chat_history.append(("User", query))
    st.session_state.chat_history.append(("AI", final_answer))

# =============================
# CHAT DISPLAY
# =============================
st.divider()
st.subheader("💬 Conversation")

for role,msg in st.session_state.chat_history:
    if role=="User":
        st.markdown(f"""
        <div style='background:#1f2937;padding:10px;border-radius:8px;margin-bottom:8px'>
        <b>🧑 You:</b><br>{msg}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='background:#111827;padding:10px;border-radius:8px;margin-bottom:8px'>
        <b>🤖 AI:</b><br>{msg}
        </div>
        """, unsafe_allow_html=True)

# =============================
# RESET SYSTEM
# =============================
st.sidebar.divider()

if st.sidebar.button("Reset System"):
    index = faiss.IndexHNSWFlat(EMBEDDING_DIM, 32)
    index.hnsw.efSearch = 50
    index.hnsw.efConstruction = 40
    st.session_state.index = index
    st.session_state.metadata = []
    st.session_state.chat_history = []

    if os.path.exists(INDEX_FILE):
        os.remove(INDEX_FILE)
    if os.path.exists(META_FILE):
        os.remove(META_FILE)

    st.sidebar.success("System Reset Complete")
