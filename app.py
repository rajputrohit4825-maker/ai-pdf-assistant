import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

# Page Config
st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📄",
    layout="wide"
)

# OpenAI Client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Load Embedding Model
model = SentenceTransformer("all-MiniLM-L6-v2")

st.title("📄 Professional AI PDF Assistant")

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

    # Chunk text
    chunks = text.split(". ")
    chunks = [chunk.strip() for chunk in chunks if len(chunk) > 40]

    # Create embeddings
    embeddings = model.encode(chunks)

    # -------------------------
    # GPT Question Section
    # -------------------------

    st.divider()
    st.subheader("🤖 Ask Questions From PDF")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_question = st.text_input("Ask a question about this document")

    if user_question:

        # Embed question
        query_embedding = model.encode([user_question])

        # Similarity search
        similarities = np.dot(embeddings, query_embedding.T).flatten()
        top_indices = similarities.argsort()[-3:][::-1]

        context = "\n\n".join([chunks[i] for i in top_indices])

        with st.spinner("AI is thinking..."):

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Answer clearly and professionally using the provided document context."
                    },
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion:\n{user_question}"
                    }
                ],
            )

            answer = response.choices[0].message.content

        # Save chat
        st.session_state.chat_history.append(("user", user_question))
        st.session_state.chat_history.append(("assistant", answer))

    # Show chat
    for role, message in st.session_state.chat_history:
        if role == "user":
            st.markdown(f"**🧑 You:** {message}")
        else:
            st.markdown(f"**🤖 AI:** {message}")

else:
    st.info("Upload a PDF file to get started.")
