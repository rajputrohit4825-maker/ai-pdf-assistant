import streamlit as st
from PyPDF2 import PdfReader

st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# ------------------------
# Sidebar
# ------------------------

st.sidebar.title("📄 AI PDF Assistant")
st.sidebar.info(
    """
    Upload a PDF and:
    - Extract text
    - Search inside document
    - Download extracted content
    """
)

# ------------------------
# Main Title
# ------------------------

st.title("📄 Professional PDF Assistant")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    with st.spinner("Reading PDF... Please wait"):
        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted

    st.success("PDF processed successfully ✅")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔍 Search Inside PDF")
        search_query = st.text_input("Enter keyword to search")

        if search_query:
            if search_query.lower() in text.lower():
                st.success("Keyword found in document ✅")
            else:
                st.error("Keyword not found ❌")

    with col2:
        st.subheader("📥 Download Extracted Text")
        st.download_button(
            label="Download as TXT",
            data=text,
            file_name="extracted_text.txt"
        )

    st.subheader("📖 Preview (First 3000 Characters)")
    st.text_area("Extracted Content", text[:3000], height=300)

else:
    st.info("Upload a PDF file to get started.")
