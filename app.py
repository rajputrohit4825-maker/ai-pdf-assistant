import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re

# -------------------------------------------------
# Page Config
# -------------------------------------------------
st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# -------------------------------------------------
# Custom Dark Theme
# -------------------------------------------------
st.markdown("""
<style>
body { background-color: #0E1117; }

[data-testid="stMetric"] {
    background-color: #1E2228;
    padding: 15px;
    border-radius: 12px;
    text-align: center;
}

.stButton>button {
    background-color: #2962FF;
    color: white;
    border-radius: 8px;
    height: 45px;
    width: 100%;
    font-weight: 600;
}

.stDownloadButton>button {
    background-color: #00C853;
    color: white;
    border-radius: 8px;
    height: 45px;
    width: 100%;
    font-weight: 600;
}

.block-container { padding-top: 2rem; }

footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
st.sidebar.markdown("## 📄 AI PDF Assistant")
st.sidebar.markdown("### Features")
st.sidebar.markdown("""
- Multi-PDF Upload  
- Smart Keyword Highlight  
- Semantic AI Search  
- Multi Answer Retrieval  
- Download Processed Text  
""")

# -------------------------------------------------
# Header
# -------------------------------------------------
colA, colB = st.columns([1, 6])
with colA:
    st.image("https://cdn-icons-png.flaticon.com/512/337/337946.png", width=60)
with colB:
    st.markdown("## Professional AI PDF Knowledge Base")
    st.caption("AI Powered Multi-Document Intelligence System")

# -------------------------------------------------
# Multi PDF Upload
# -------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload one or more PDF files",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:

    text = ""
    total_pages = 0

    with st.spinner("Analyzing documents..."):
        for file in uploaded_files:
            reader = PdfReader(file)
            total_pages += len(reader.pages)

            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted

    st.success("Documents analyzed successfully. AI is ready.")

    # -------------------------------------------------
    # Stats
    # -------------------------------------------------
    total_words = len(text.split())
    total_chars = len(text)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pages", total_pages)
    col2.metric("Total Words", total_words)
    col3.metric("Total Characters", total_chars)

    st.divider()

    # -------------------------------------------------
    # Search & Highlight
    # -------------------------------------------------
    st.subheader("🔍 Search Inside Documents")

    search_query = st.text_input("Enter keyword to highlight")

    preview_text = text[:3000]

    if search_query:
        pattern = re.compile(search_query, re.IGNORECASE)
        preview_text = pattern.sub(
            f"<mark>{search_query}</mark>", preview_text
        )

    st.markdown(preview_text, unsafe_allow_html=True)

    st.divider()

    # -------------------------------------------------
    # AI Semantic Chat
    # -------------------------------------------------
    st.subheader("🤖 Ask AI About Your Documents")

    @st.cache_resource(show_spinner=False)
    def load_model():
        return SentenceTransformer("all-MiniLM-L6-v2")

    model = load_model()

    # Paragraph chunking
    chunks = text.split("\n")
    chunks = [c.strip() for c in chunks if len(c) > 50]

    if chunks:

        embeddings = model.encode(chunks)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_question = st.chat_input("Ask something about your documents")

        if user_question:
            query_embedding = model.encode([user_question])
            similarities = np.dot(embeddings, query_embedding.T).flatten()

            top_indices = similarities.argsort()[-3:][::-1]
            best_match = "\n\n".join([chunks[i] for i in top_indices])

            st.session_state.chat_history.append(("user", user_question))
            st.session_state.chat_history.append(("assistant", best_match))

        for role, message in st.session_state.chat_history:
            with st.chat_message(role):
                st.write(message)

    st.divider()

    # -------------------------------------------------
    # Download
    # -------------------------------------------------
    st.download_button(
        label="📥 Download Combined Extracted Text",
        data=text,
        file_name="combined_extracted_text.txt"
    )

else:
    st.info("Upload one or more PDF files to get started.")

st.divider()
st.caption("Built with Python, Streamlit & Semantic AI | Enterprise Portfolio Project")
