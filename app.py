import streamlit as st
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="AI PDF Platform Secure", layout="wide")

# ---------------- DB SETUP ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    reset_token TEXT,
    token_expiry TEXT
)
""")
conn.commit()

# ---------------- SECURITY ----------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

# ---------------- AUTH FUNCTIONS ----------------
def register_user(username, password):
    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute("SELECT password FROM users WHERE username=?", (username,))
    result = cursor.fetchone()
    if result and verify_password(password, result[0]):
        return True
    return False

def generate_reset_token(username):
    token = secrets.token_hex(16)
    expiry = datetime.now() + timedelta(minutes=10)

    cursor.execute("""
        UPDATE users
        SET reset_token=?, token_expiry=?
        WHERE username=?
    """, (token, expiry.isoformat(), username))
    conn.commit()

    return token

def reset_password(token, new_password):
    cursor.execute("""
        SELECT username, token_expiry
        FROM users
        WHERE reset_token=?
    """, (token,))
    result = cursor.fetchone()

    if result:
        expiry_time = datetime.fromisoformat(result[1])
        if datetime.now() < expiry_time:
            cursor.execute("""
                UPDATE users
                SET password=?, reset_token=NULL, token_expiry=NULL
                WHERE reset_token=?
            """, (hash_password(new_password), token))
            conn.commit()
            return True

    return False

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- LOGIN SYSTEM ----------------
if not st.session_state.logged_in:

    st.title("🔐 Secure Login System")

    menu = st.radio("Select Option", ["Login", "Register", "Forgot Password", "Reset Password"])

    if menu == "Register":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            if register_user(username, password):
                st.success("Account created successfully")
            else:
                st.error("Username already exists")

    if menu == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials")

    if menu == "Forgot Password":
        username = st.text_input("Enter your username")
        if st.button("Generate Reset Token"):
            token = generate_reset_token(username)
            st.info(f"Your reset token (valid 10 min): {token}")

    if menu == "Reset Password":
        token = st.text_input("Enter Reset Token")
        new_password = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            if reset_password(token, new_password):
                st.success("Password reset successfully")
            else:
                st.error("Invalid or expired token")

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:

    st.sidebar.success(f"Logged in as {st.session_state.username}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📄 AI PDF Platform – Secure Mode")
    st.success("Phase 1 Security Upgrade Active")
