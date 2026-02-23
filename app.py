import streamlit as st
from PyPDF2 import PdfReader
from openai import OpenAI

st.set_page_config(page_title="Fast AI PDF Assistant", layout="wide")
st.title("⚡ Fast AI PDF Assistant")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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
        st.subheader("💬 Ask AI About This PDF")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_question = st.text_input("Ask a question")

        if st.button("Ask AI") and user_question:

            with st.spinner("AI is thinking..."):

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Answer clearly based on the provided document."
                        },
                        {
                            "role": "user",
                            "content": f"Document:\n{text[:8000]}\n\nQuestion:\n{user_question}"
                        }
                    ]
                )

                answer = response.choices[0].message.content

            st.session_state.chat_history.append(("You", user_question))
            st.session_state.chat_history.append(("AI", answer))

        for role, message in st.session_state.chat_history:
            st.markdown(f"**{role}:** {message}")

else:
    st.info("Upload a PDF file to get started.")
