import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

# Load OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="AI PDF Assistant", layout="wide")

st.title("📄 Professional AI PDF Assistant")

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    st.success("PDF processed successfully ✅")

    st.subheader("📖 Preview")
    st.text_area("Extracted Content", text[:3000], height=250)

    st.divider()
    st.subheader("💬 Ask AI About This PDF")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_question = st.text_input("Ask a question from this document")

    if st.button("Ask AI") and user_question:

        chunks = text.split(". ")
        chunks = [c.strip() for c in chunks if len(c) > 40]

        if len(chunks) == 0:
            st.error("Document too small for AI processing.")
        else:
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(chunks)

            query_embedding = model.encode([user_question])
            similarities = np.dot(embeddings, query_embedding.T).flatten()

            top_indices = similarities.argsort()[-3:][::-1]
            context = "\n\n".join([chunks[i] for i in top_indices])

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Answer clearly using the provided document context."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{user_question}"}
                ]
            )

            answer = response.choices[0].message.content

            st.session_state.chat_history.append(("You", user_question))
            st.session_state.chat_history.append(("AI", answer))

    for role, message in st.session_state.chat_history:
        st.markdown(f"**{role}:** {message}")

else:
    st.info("Upload a PDF file to get started.")
