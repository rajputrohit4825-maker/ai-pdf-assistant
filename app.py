import streamlit as st
import pickle
import faiss
import os
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from googletrans import Translator

st.set_page_config(page_title="FEEE AI Assistant", page_icon="🤖")

translator = Translator()

# ----------------------------
# Build Vector DB From Uploaded PDF
# ----------------------------

def build_vector_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    texts = text.split("\n")

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(texts)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return model, index, texts

# ----------------------------
# Session State
# ----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "model" not in st.session_state:
    st.session_state.model = None
    st.session_state.index = None
    st.session_state.texts = None

# ----------------------------
# Sidebar PDF Upload
# ----------------------------

st.sidebar.title("📂 Upload PDF")

uploaded_file = st.sidebar.file_uploader("Upload your PDF", type=["pdf"])

if uploaded_file is not None:
    st.sidebar.success("PDF uploaded successfully!")

    model, index, texts = build_vector_from_pdf(uploaded_file)

    st.session_state.model = model
    st.session_state.index = index
    st.session_state.texts = texts

    st.sidebar.success("Vector database created!")

# ----------------------------
# Search Function
# ----------------------------

def search(query, k=3):
    model = st.session_state.model
    index = st.session_state.index
    texts = st.session_state.texts

    query_embedding = model.encode([query])
    D, I = index.search(query_embedding, k)

    return [texts[i] for i in I[0]]

# ----------------------------
# UI
# ----------------------------

st.title("🤖 AI PDF Assistant")

if st.session_state.model is None:
    st.info("Please upload a PDF to start chatting.")
else:

    # Show chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask your question..."):

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        detected_lang = translator.detect(prompt).lang
        translated_query = translator.translate(prompt, dest="en").text

        results = search(translated_query)
        answer = " ".join(results)

        if detected_lang == "hi":
            final_answer = translator.translate(answer, dest="hi").text
        else:
            final_answer = answer

        with st.chat_message("assistant"):
            st.markdown(final_answer)

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
