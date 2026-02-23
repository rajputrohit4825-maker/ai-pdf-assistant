import streamlit as st
from PyPDF2 import PdfReader
import re

# ---------------- Page Config ----------------
st.set_page_config(page_title="AI PDF Assistant", layout="wide")

st.title("📄 AI PDF Assistant")
st.caption("Fast Search • Hindi + English Support")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

# ---------------- PDF Processing ----------------
if uploaded_file:

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"

    if not text.strip():
        st.error("No readable text found in this PDF.")
        st.stop()

    st.success("PDF processed successfully ✅")

    # Split sentences (Hindi + English)
    sentences = re.split(r"[.\n।]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    st.divider()
    st.subheader("🔎 Search in Document")

    query = st.text_input("Type your question")

    if query:

        query_lower = query.lower()
        results = []

        for sentence in sentences:
            if query_lower in sentence.lower():
                results.append(sentence)

        if results:
            st.markdown(f"### Found {len(results)} Results")
            for result in results[:5]:
                highlighted = re.sub(
                    query,
                    f"**{query}**",
                    result,
                    flags=re.IGNORECASE
                )
                st.write("•", highlighted)
        else:
            st.warning("No exact match found. Try different keywords.")

else:
    st.info("Upload a PDF to start.")
