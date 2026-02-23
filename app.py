 import streamlit as st
from PyPDF2 import PdfReader
import re

st.set_page_config(page_title="Pro AI PDF Assistant", layout="wide")

# ---------------- DARK STYLE ----------------
st.markdown("""
<style>
body { background-color: #0E1117; color: white; }
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
</style>
""", unsafe_allow_html=True)

st.title("📄 Pro AI PDF Assistant")
st.caption("Live Search • Highlighted Results • Hindi + English")

# ---------------- SIDEBAR ----------------
st.sidebar.title("⚙ Settings")
min_length = st.sidebar.slider("Minimum Sentence Length", 10, 100, 20)
max_results = st.sidebar.slider("Max Results", 1, 10, 5)

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

# ---------------- PROCESS PDF ----------------
if uploaded_file:

    if "sentences_data" not in st.session_state:

        reader = PdfReader(uploaded_file)
        page_map = []

        for page_number, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text()
            if extracted:
                split_sentences = re.split(r"[.\n।]", extracted)
                for sentence in split_sentences:
                    clean = sentence.strip()
                    if len(clean) > min_length:
                        page_map.append((clean, clean.lower(), page_number))

        if not page_map:
            st.error("This PDF appears to be scanned or unreadable.")
            st.stop()

        st.session_state.sentences_data = page_map
        st.success("PDF processed successfully ✅")

    sentences_data = st.session_state.sentences_data

    st.divider()
    st.subheader("💬 Live Smart Search")

    user_question = st.text_input("Type your question (Hindi or English)")

    if user_question:

        # -------- STOP WORDS --------
        stop_words = {
            "what","is","the","a","an","of","in","to","and",
            "क्या","है","और","का","की","के","को","में"
        }

        question_words = [
            word for word in user_question.lower().split()
            if word not in stop_words and len(word) > 2
        ]

        results = []

        for original, lower_version, page_number in sentences_data:

            score = 0

            for word in question_words:
                if word in lower_version:
                    score += 2
                elif any(word in w for w in lower_version.split()):
                    score += 1

            if score > 0:
                results.append((score, original, page_number))

        # If still nothing matched, fallback to loose match
        if not results:
            for original, lower_version, page_number in sentences_data:
                if any(word in lower_version for word in question_words):
                    results.append((1, original, page_number))

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

            st.download_button(
                label="📥 Export Results",
                data=export_text,
                file_name="search_results.txt",
                mime="text/plain"
            )

        else:
            st.warning("No relevant answer found in this document.")

else:
    st.info("Upload a PDF file to get started.")
