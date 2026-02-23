import streamlit as st
from PyPDF2 import PdfReader
import re

st.set_page_config(page_title="Ultra Fast AI PDF Assistant", layout="wide")
st.title("⚡ Ultra Fast AI PDF Assistant (20x Speed)")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    # -------- PROCESS ONLY ONCE --------
    if "sentences_data" not in st.session_state:

        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        if len(text.strip()) == 0:
            st.error("This PDF appears to be scanned or image-based.")
            st.stop()

        # Split once
        raw_sentences = re.split(r"[.\n।]", text)

        # Clean + store lowercase version for fast search
        sentences_data = []
        for s in raw_sentences:
            clean = s.strip()
            if len(clean) > 20:
                sentences_data.append((clean, clean.lower()))

        st.session_state.sentences_data = sentences_data

        st.success("PDF processed successfully ✅")

    sentences_data = st.session_state.sentences_data

    st.divider()
    st.subheader("💬 Ask Question From PDF")

    user_question = st.text_input("Ask a question (Hindi or English)")

    if st.button("Search Answer") and user_question:

        question_words = user_question.lower().split()

        best_matches = []

        # Ultra light search
        for original, lower_version in sentences_data:
            score = 0
            for word in question_words:
                if word in lower_version:
                    score += 1

            if score:
                best_matches.append((score, original))

        if best_matches:
            best_matches.sort(reverse=True)

            st.success("Top Relevant Answers ✅")

            for match in best_matches[:3]:
                st.write("👉", match[1])
        else:
            st.warning("No relevant answer found.")

else:
    st.info("Upload a PDF file to get started.")
