import streamlit as st
from PyPDF2 import PdfReader
import re

st.set_page_config(page_title="Pro AI PDF Assistant", layout="wide")
st.title("📄 Pro AI PDF Assistant")
st.caption("Live Search • Highlighted Answers • Hindi + English Support")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    # -------- Process Only Once --------
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

        raw_sentences = re.split(r"[.\n।]", text)

        sentences_data = []
        for s in raw_sentences:
            clean = s.strip()
            if len(clean) > 20:
                sentences_data.append((clean, clean.lower()))

        st.session_state.sentences_data = sentences_data
        st.success("PDF processed successfully ✅")

    sentences_data = st.session_state.sentences_data

    st.divider()
    st.subheader("🔍 Live Search")

    user_question = st.text_input("Type your question (results appear instantly)")

    if user_question:

        question_words = user_question.lower().split()
        results = []

        for original, lower_version in sentences_data:
            score = sum(word in lower_version for word in question_words)
            if score > 0:
                results.append((score, original))

        if results:
            results.sort(reverse=True)

            st.markdown("### 📌 Top Matches")

            for score, sentence in results[:5]:

                highlighted = sentence
                for word in question_words:
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    highlighted = pattern.sub(
                        f"<mark>{word}</mark>", highlighted
                    )

                st.markdown(
                    f"<div style='padding:10px; border-radius:10px; background:#f5f5f5; margin-bottom:10px;'>{highlighted}</div>",
                    unsafe_allow_html=True
                )

        else:
            st.warning("No relevant answer found.")

else:
    st.info("Upload a PDF file to get started.")
