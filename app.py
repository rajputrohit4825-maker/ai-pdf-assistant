import streamlit as st
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from datetime import datetime
import bcrypt

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="AI PDF Platform", layout="wide")
st.title("📄 AI PDF Platform")

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# -------------------------------
# PASSWORD HELPERS
# -------------------------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# -------------------------------
# SESSION INIT
# -------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

# -------------------------------
# AUTH FUNCTIONS
# -------------------------------
def register():
    st.subheader("Create Account")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if not username or not password:
            st.error("All fields required")
            return

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO users (username, password_hash)
                        VALUES (:username, :password)
                    """),
                    {
                        "username": username.strip(),
                        "password": hash_password(password)
                    }
                )
            st.success("Account created. You can login now.")
        except:
            st.error("Username already exists")


def login():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT password_hash FROM users WHERE username=:username"),
                {"username": username.strip()}
            ).fetchone()

        if result and verify_password(password, result[0]):
            st.session_state.user = username.strip()
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid username or password")


def forgot_password():
    st.subheader("Reset Password")
    username = st.text_input("Username")
    new_password = st.text_input("New Password", type="password")

    if st.button("Reset Password"):
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT id FROM users WHERE username=:username"),
                {"username": username.strip()}
            ).fetchone()

            if result:
                conn.execute(
                    text("""
                        UPDATE users
                        SET password_hash=:password
                        WHERE username=:username
                    """),
                    {
                        "username": username.strip(),
                        "password": hash_password(new_password)
                    }
                )
                st.success("Password updated successfully")
            else:
                st.error("User not found")

# -------------------------------
# AUTH ROUTING
# -------------------------------
if not st.session_state.user:
    menu = st.radio("Select Option", ["Login", "Register", "Forgot Password"])

    if menu == "Login":
        login()
    elif menu == "Register":
        register()
    else:
        forgot_password()

    st.stop()

# -------------------------------
# LOGGED IN UI
# -------------------------------
st.sidebar.success(f"Logged in as: {st.session_state.user}")

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# -------------------------------
# LOAD EMBEDDING MODEL
# -------------------------------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# -------------------------------
# PDF UPLOAD
# -------------------------------
st.subheader("Upload PDF")
uploaded_file = st.file_uploader("Upload your PDF", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    text_content = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_content += page_text

    if not text_content.strip():
        st.error("No readable text found")
    else:
        chunks = [text_content[i:i+500] for i in range(0, len(text_content), 500)]
        st.write("Chunks created:", len(chunks))

        if st.button("Index Document"):
            with engine.begin() as conn:
                for chunk in chunks:
                    embedding = model.encode(chunk).tolist()
                    vector_str = "[" + ",".join(map(str, embedding)) + "]"

                    conn.execute(
                        text("""
                            INSERT INTO documents
                            (username, content, embedding_vector, created_at)
                            VALUES
                            (:username, :content,
                             CAST(:embedding AS vector),
                             :created_at)
                        """),
                        {
                            "username": st.session_state.user,
                            "content": chunk,
                            "embedding": vector_str,
                            "created_at": datetime.utcnow()
                        }
                    )

            st.success("Document indexed successfully")

# -------------------------------
# SEARCH
# -------------------------------
st.divider()
st.subheader("Ask a Question")

query = st.text_input("Enter question")

if st.button("Search") and query:
    query_vector = model.encode(query).tolist()
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"

    with engine.connect() as conn:
        results = conn.execute(
            text("""
                SELECT content,
                       1 - (embedding_vector <=> CAST(:query_vector AS vector)) AS similarity
                FROM documents
                WHERE username = :username
                ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
                LIMIT 3;
            """),
            {
                "username": st.session_state.user,
                "query_vector": vector_str
            }
        ).fetchall()

    if results:
        for row in results:
            st.write("•", row[0])
    else:
        st.warning("No relevant answer found")

# -------------------------------
# STATS
# -------------------------------
with engine.connect() as conn:
    count = conn.execute(
        text("SELECT COUNT(*) FROM documents WHERE username=:username"),
        {"username": st.session_state.user}
    ).scalar()

st.sidebar.write("Indexed Chunks:", count)
