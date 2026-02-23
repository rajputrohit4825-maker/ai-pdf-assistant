import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re
from fpdf import FPDF

# -------------------------------------------------
# Page Config
# -------------------------------------------------
st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# -------------------------------------------------
# Dark Theme Styling
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
st.sidebar.markdown("## 📄 AI PDF Intelligence System")
st.sidebar.markdown("""
### Features
- Multi PDF Upload  
- Smart Highlight  
- Bullet Summary  
- Semantic AI Chat  
- Export Answers as PDF  
""")

# -------------------------------------------------
# Header
# -------------------------------------------------
st.title("Professional AI PDF Knowledge Base")
st.caption("Advanced Multi-Document Intelligence Engine")

# -------------------------------------------------
# Upload PDFs
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

    st.success("Documents analyzed successfully")

    # Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Pages", total_pages)
    col2.metric("Words", len(text.split()))
    col3.metric("Characters", len(text))

    st.divider()

    # -------------------------------------------------
    # Highlight Search
    # -------------------------------------------------
    st.subheader("Search & Highlight")
    search_query = st.text_input("Enter keyword")

    preview_text = text[:3000]

    if search_query:
        pattern = re.compile(search_query, re.IGNORECASE)
        preview_text = pattern.sub(
            f"<mark>{search_query}</mark>", preview_text
        )

    st.markdown(preview_text, unsafe_allow_html=True)

    st.divider()

    # -------------------------------------------------
    # Smart Bullet Summary
    # -------------------------------------------------
    st.subheader("Smart Bullet Summary")

    if st.button("Generate Summary"):
        sentences = text.split(".")
        sentences = [s.strip() for s in sentences if len(s) > 60]

        if sentences:
            summary_points = sentences[:5]
            st.success("Key Points:")
            for point in summary_points:
                st.markdown(f"- {point}")
        else:
            st.write("Document too short for summary.")

    st.divider()

    # -------------------------------------------------
    # AI Semantic Chat
    # -------------------------------------------------
    st.subheader("Ask AI About Your Documents")

    @st.cache_resource(show_spinner=False)
    def load_model():
        return SentenceTransformer("all-MiniLM-L6-v2")

    model = load_model()

    chunks = text.split("\n")
    chunks = [c.strip() for c in chunks if len(c) > 50]

    if chunks:

        embeddings = model.encode(chunks)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        colA, colB = st.columns([4,1])
        with colA:
            user_question = st.chat_input("Ask something about your documents")
        with colB:
            if st.button("Clear Chat"):
                st.session_state.chat_history = []

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

        # -------------------------------------------------
        # Export Chat as PDF
        # -------------------------------------------------
        if st.session_state.chat_history:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=10)

            for role, message in st.session_state.chat_history:
                pdf.multi_cell(0, 8, f"{role.upper()}: {message}")
                pdf.ln()

            pdf_output = pdf.output(dest="S").encode("latin-1")

            st.download_button(
                label="Download Chat as PDF",
                data=pdf_output,
                file_name="ai_chat_export.pdf"
            )

else:
    st.info("Upload PDF files to begin.")

st.divider()
st.caption("Enterprise AI PDF System | Built with Python & Semantic Search")
