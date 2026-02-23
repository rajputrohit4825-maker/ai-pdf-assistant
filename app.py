import streamlit as st
from PyPDF2 import PdfReader

st.set_page_config(page_title="Smart Free AI PDF Assistant", layout="wide")
st.title("📄 Smart Free AI PDF Assistant")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"

    if len(text.strip()) == 0:
        st.error("This PDF appears to be scanned or image-based.")
    else:
        st.success("PDF processed successfully ✅")

        st.subheader("📖 Preview")
        st.text_area("Extracted Text", text[:1500], height=200)

        st.divider()
        st.subheader("💬 Ask Question From PDF")

        user_question = st.text_input("Ask a question")

        if st.button("Search Answer") and user_question:

            sentences = text.split(". ")
            question_words = user_question.lower().split()

            scored_sentences = []

            for sentence in sentences:
                score = 0
                for word in question_words:
                    if word in sentence.lower():
                        score += 1

                if score > 0:
                    scored_sentences.append((score, sentence.strip()))

            if scored_sentences:
                # Sort by highest score
                scored_sentences.sort(reverse=True)

                st.success("Top Relevant Answers ✅")

                for i in range(min(3, len(scored_sentences))):
                    st.write(f"👉 {scored_sentences[i][1]}")

            else:
                st.warning("No relevant answer found in this document.")

else:
    st.info("Upload a PDF file to get started.")
