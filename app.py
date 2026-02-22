import streamlit as st
from PyPDF2 import PdfReader
import re

st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# Sidebar
st.sidebar.title("📄 AI PDF Assistant")
st.sidebar.info(
    """
    Professional PDF Processing Tool
    
    ✔ Extract Text  
    ✔ Search & Highlight  
    ✔ Download Content  
    ✔ View Statistics
    """
)

st.title("📄 Professional PDF Assistant")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    with st.spinner("Reading PDF..."):
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted

    st.success("PDF processed successfully ✅")

    # Stats
    total_pages = len(reader.pages)
    total_words = len(text.split())
    total_chars = len(text)

    col1, col2, col3 = st.columns(3)
    col1.metric("Pages", total_pages)
    col2.metric("Words", total_words)
    col3.metric("Characters", total_chars)

    st.divider()

    # Search
    st.subheader("🔍 Search & Highlight")
    search_query = st.text_input("Enter keyword")

    preview_text = text[:3000]

    if search_query:
        pattern = re.compile(search_query, re.IGNORECASE)
        preview_text = pattern.sub(
            f"<mark>{search_query}</mark>", preview_text
        )

    st.markdown(preview_text, unsafe_allow_html=True)

    st.divider()

    # Download
    st.download_button(
        label="📥 Download Extracted Text",
        data=text,
        file_name="extracted_text.txt"
    )

else:
    st.info("Upload a PDF file to get started.")

st.divider()
st.caption("Built with ❤️ using Streamlit")
