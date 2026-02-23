import streamlit as st
from PyPDF2 import PdfReader

st.set_page_config(page_title="Free AI PDF Assistant", layout="wide")
st.title("📄 Free AI PDF Assistant (No API Needed)")

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
            best_match = ""

            for sentence in sentences:
                if user_question.lower() in sentence.lower():
                    best_match = sentence
                    break

            if best_match:
                st.success("Answer Found ✅")
                st.write(best_match)
            else:
                st.warning("Exact match not found. Showing closest content:")
                st.write(sentences[:3])

else:
    st.info("Upload a PDF file to get started.")
