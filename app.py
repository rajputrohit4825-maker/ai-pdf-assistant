import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

# -------------------- Setup --------------------

st.set_page_config(page_title="AI PDF Assistant", layout="wide")
st.title("📄 Professional AI PDF Assistant")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Cache embedding model (load only once)
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -------------------- Upload --------------------

uploaded_file = st.file_uploader("Upload your PDF file", type="pdf")

if uploaded_file:

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        try:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        except:
            pass

    st.success("PDF processed successfully ✅")
    st.write("Text Length:", len(text))

    if len(text.strip()) == 0:
        st.error("This PDF appears to be scanned or image-based.")
    else:

        st.subheader("📖 Preview")
        st.text_area("Extracted Text", text[:2000], height=200)

        # -------------------- Create Chunks & Embeddings (ONE TIME) --------------------

        chunks = text.split(". ")
        chunks = [c.strip() for c in chunks if len(c) > 5]

        if "embeddings" not in st.session_state:
            st.session_state.embeddings = model.encode(chunks)
            st.session_state.chunks = chunks

        embeddings = st.session_state.embeddings
        chunks = st.session_state.chunks

        # -------------------- AI Chat --------------------

        st.divider()
        st.subheader("💬 Ask AI About This PDF")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_question = st.text_input("Ask a question from this document")

        if st.button("Ask AI") and user_question:

            query_embedding = model.encode([user_question])
            similarities = np.dot(embeddings, query_embedding.T).flatten()

            top_indices = similarities.argsort()[-3:][::-1]
            context = "\n\n".join([chunks[i] for i in top_indices])

            with st.spinner("AI is thinking..."):

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

        # Display chat
        for role, message in st.session_state.chat_history:
            st.markdown(f"**{role}:** {message}")

else:
    st.info("Upload a PDF file to get started.")
