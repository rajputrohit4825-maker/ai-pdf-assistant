import streamlit as st
import random
import smtplib
import bcrypt
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# -------------------------
# CONFIG
# -------------------------

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

st.set_page_config(page_title="Auth System", layout="centered")
st.title("AI PDF Platform - Auth")

# -------------------------
# EMAIL FUNCTION
# -------------------------

def send_otp_email(to_email, otp):
    try:
        msg = MIMEText(f"""
Your OTP is: {otp}
Valid for 10 minutes.
""")

        msg["Subject"] = "Password Reset OTP"
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)

        return True

    except Exception as e:
        st.error(f"Email error: {e}")
        return False

# -------------------------
# CREATE USERS TABLE
# -------------------------

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT
        )
    """))

# -------------------------
# SESSION
# -------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------------
# REGISTER
# -------------------------

st.subheader("Register")

reg_email = st.text_input("Email", key="reg_email")
reg_password = st.text_input("Password", type="password", key="reg_pass")

if st.button("Register"):
    if reg_email and reg_password:
        hashed = bcrypt.hashpw(reg_password.encode(), bcrypt.gensalt()).decode()

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO users (email, password) VALUES (:email, :password)"),
                    {"email": reg_email, "password": hashed}
                )
            st.success("Registration successful")
        except:
            st.error("Email already exists")

# -------------------------
# LOGIN
# -------------------------

st.subheader("Login")

login_email = st.text_input("Email", key="login_email")
login_password = st.text_input("Password", type="password", key="login_pass")

if st.button("Login"):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT password FROM users WHERE email = :email"),
            {"email": login_email}
        ).fetchone()

    if result and bcrypt.checkpw(login_password.encode(), result[0].encode()):
        st.session_state.logged_in = True
        st.session_state.user_email = login_email
        st.success("Login successful")
    else:
        st.error("Invalid credentials")

# -------------------------
# FORGOT PASSWORD
# -------------------------

st.subheader("Forgot Password")

forgot_email = st.text_input("Enter your registered email")

if st.button("Send OTP"):
    if forgot_email:
        otp = str(random.randint(100000, 999999))

        st.session_state.reset_otp = otp
        st.session_state.reset_email = forgot_email
        st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        if send_otp_email(forgot_email, otp):
            st.success("OTP sent to your email")

# -------------------------
# OTP VERIFY + RESET
# -------------------------

if "reset_otp" in st.session_state:

    entered_otp = st.text_input("Enter OTP")
    new_password = st.text_input("New Password", type="password")

    if st.button("Reset Password"):

        if datetime.utcnow() > st.session_state.otp_expiry:
            st.error("OTP expired")

        elif entered_otp == st.session_state.reset_otp:

            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE users
                        SET password = :password
                        WHERE email = :email
                    """),
                    {
                        "password": hashed,
                        "email": st.session_state.reset_email
                    }
                )

            st.success("Password reset successful")
            del st.session_state.reset_otp

        else:
            st.error("Invalid OTP")

# -------------------------
# LOGOUT
# -------------------------

if st.session_state.logged_in:
    st.success(f"Logged in as {st.session_state.user_email}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
