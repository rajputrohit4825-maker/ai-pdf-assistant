import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import re

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("📄 AI PDF Assistant")
st.sidebar.info(
    """
    Professional AI Powered PDF Tool

    ✔ Extract Text
    ✔ Smart Search
    ✔ AI Question Answering
    ✔ Download Content
    """
)

st.title("📄 Professional AI PDF Assistant")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    # ----------------------------
    # Read PDF
    # ----------------------------
    with st.spinner("Reading PDF..."):
        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted

    st.success("PDF processed successfully ✅")

    # ----------------------------
    # Stats
    # ----------------------------
    total_pages = len(reader.pages)
    total_words = len(text.split())
    total_chars = len(text)

    col1, col2, col3 = st.columns(3)
    col1.metric("Pages", total_pages)
    col2.metric("Words", total_words)
    col3.metric("Characters", total_chars)

    st.divider()

    # ----------------------------
    # Search + Highlight
    # ----------------------------
    st.subheader("🔍 Search Inside PDF")

    search_query = st.text_input("Enter keyword to highlight")

    preview_text = text[:3000]

    if search_query:
        pattern = re.compile(search_query, re.IGNORECASE)
        preview_text = pattern.sub(
            f"<mark>{search_query}</mark>", preview_text
        )

    st.markdown(preview_text, unsafe_allow_html=True)

    st.divider()

    # ----------------------------
    # AI Semantic Search
    # ----------------------------
    st.subheader("🤖 Ask AI About Your PDF")

    # Load model only once
    @st.cache_resource
    def load_model():
        return SentenceTransformer("all-MiniLM-L6-v2")

    model = load_model()

    sentences = text.split(".")
    sentences = [s.strip() for s in sentences if len(s) > 20]

    if sentences:
        embeddings = model.encode(sentences)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_question = st.chat_input("Ask something about your document")

        if user_question:
            query_embedding = model.encode([user_question])
            similarities = np.dot(embeddings, query_embedding.T).flatten()
            best_match = sentences[similarities.argmax()]

            st.session_state.chat_history.append(("user", user_question))
            st.session_state.chat_history.append(("assistant", best_match))

        for role, message in st.session_state.chat_history:
            with st.chat_message(role):
                st.write(message)

    st.divider()

    # ----------------------------
    # Download
    # ----------------------------
    st.download_button(
        label="📥 Download Extracted Text",
        data=text,
        file_name="extracted_text.txt"
    )

else:
    st.info("Upload a PDF file to get started.")

st.divider()
st.caption("Built with Python, Streamlit & AI")
