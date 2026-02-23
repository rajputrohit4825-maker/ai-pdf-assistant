import streamlit as st
from PyPDF2 import PdfReader
import re

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Pro AI PDF Assistant", layout="wide")

# ---------------- DARK MODE STYLE ----------------
st.markdown("""
<style>
body { background-color: #0E1117; color: white; }
.block-container { padding-top: 2rem; }
.chat-box {
    padding: 12px;
    border-radius: 12px;
    margin-bottom: 10px;
    background-color: #1E1E1E;
}
mark {
    background-color: #ffcc00;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}
.header {
    font-size:28px;
    font-weight:bold;
}
.subheader {
    font-size:16px;
    color:gray;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown("<div class='header'>📄 Pro AI PDF Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='subheader'>Live Search • Highlighted Results • Professional UI</div>", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
st.sidebar.title("⚙ Settings")
min_length = st.sidebar.slider("Minimum Sentence Length", 10, 100, 20)
max_results = st.sidebar.slider("Max Results", 1, 10, 5)

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

# ---------------- PROCESS PDF ----------------
if uploaded_file:

    if "sentences_data" not in st.session_state:

        reader = PdfReader(uploaded_file)
        text = ""
        page_map = []

        for page_number, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

                split_sentences = re.split(r"[.\n।]", extracted)
                for sentence in split_sentences:
                    clean = sentence.strip()
                    if len(clean) > min_length:
                        page_map.append((clean, clean.lower(), page_number))

        if len(text.strip()) == 0:
            st.error("This PDF appears to be scanned or image-based.")
            st.stop()

        st.session_state.sentences_data = page_map
        st.session_state.full_text = text

        st.success("PDF processed successfully ✅")

    sentences_data = st.session_state.sentences_data

    st.divider()
    st.subheader("💬 Live Question Search")

    user_question = st.text_input("Type your question (results appear instantly)")

    if user_question:

        question_words = user_question.lower().split()
        results = []

        for original, lower_version, page_number in sentences_data:
            score = sum(word in lower_version for word in question_words)
            if score > 0:
                results.append((score, original, page_number))

        if results:
            results.sort(reverse=True)

            st.markdown(f"### 🔎 {len(results)} Results Found")

            export_text = ""

            for score, sentence, page_number in results[:max_results]:

                highlighted = sentence
                for word in question_words:
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    highlighted = pattern.sub(
                        f"<mark>{word}</mark>", highlighted
                    )

                st.markdown(
                    f"<div class='chat-box'><b>📄 Page {page_number}</b><br>{highlighted}</div>",
                    unsafe_allow_html=True
                )

                export_text += f"Page {page_number}: {sentence}\n\n"

            # -------- EXPORT BUTTON --------
            st.download_button(
                label="📥 Export Results",
                data=export_text,
                file_name="search_results.txt",
                mime="text/plain"
            )

        else:
            st.warning("No relevant answer found.")

else:
    st.info("Upload a PDF file to get started.")
