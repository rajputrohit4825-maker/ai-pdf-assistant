import streamlit as st
import re
import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# ------------------------------------------------
# CONFIG
# ------------------------------------------------

st.set_page_config(page_title="AI PDF SaaS", layout="wide")

st.markdown("""
<style>
body {background-color: #0e1117; color: white;}
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed);
    color: white; border-radius: 8px;
}
section[data-testid="stSidebar"] {
    background-color: #111827;
}
</style>
""", unsafe_allow_html=True)

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

# ------------------------------------------------
# DATABASE TABLE
# ------------------------------------------------

with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        subscription_status TEXT DEFAULT 'free',
        created_at TIMESTAMP DEFAULT NOW()
    );
    """))

# ------------------------------------------------
# SESSION INIT
# ------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "query_count" not in st.session_state:
    st.session_state.query_count = 0

# ------------------------------------------------
# VALIDATION
# ------------------------------------------------

def valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def valid_password(password):
    return len(password) >= 6

# ------------------------------------------------
# EMAIL OTP
# ------------------------------------------------

def send_otp(email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}\nValid for 10 minutes.")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)
        return True
    except:
        return False

# ------------------------------------------------
# AUTH SECTION
# ------------------------------------------------

if not st.session_state.logged_in:

    st.title("🔐 AI PDF SaaS Platform")

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])

    # ---------------- LOGIN ----------------
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            with engine.connect() as conn:
                user = conn.execute(
                    text("SELECT password, role, subscription_status FROM users WHERE email=:e"),
                    {"e": email}
                ).fetchone()

            if user and bcrypt.checkpw(password.encode(), user[0].encode()):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.role = user[1]
                st.session_state.plan = user[2]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # ---------------- REGISTER ----------------
    with tab2:
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Password", type="password", key="reg_pass")

        if st.button("Register"):
            if not valid_email(reg_email):
                st.error("Invalid email format")
            elif not valid_password(reg_pass):
                st.error("Password must be 6+ characters")
            else:
                hashed = bcrypt.hashpw(reg_pass.encode(), bcrypt.gensalt()).decode()
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO users(email,password) VALUES(:e,:p)"),
                            {"e": reg_email, "p": hashed}
                        )
                    st.success("Registration successful")
                except:
                    st.error("Email already exists")

    # ---------------- FORGOT PASSWORD ----------------
    with tab3:
        forgot_email = st.text_input("Enter registered email")

        if st.button("Send OTP"):
            otp = str(random.randint(100000,999999))
            st.session_state.reset_otp = otp
            st.session_state.reset_email = forgot_email
            st.session_state.expiry = datetime.utcnow()+timedelta(minutes=10)

            if send_otp(forgot_email, otp):
                st.success("OTP sent to email")

        if "reset_otp" in st.session_state:
            entered = st.text_input("Enter OTP")
            new_pass = st.text_input("New Password", type="password")

            if st.button("Reset Password"):
                if datetime.utcnow() > st.session_state.expiry:
                    st.error("OTP expired")
                elif entered == st.session_state.reset_otp:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE users SET password=:p WHERE email=:e"),
                            {"p": hashed, "e": st.session_state.reset_email}
                        )
                    st.success("Password reset successful")
                else:
                    st.error("Invalid OTP")

# ------------------------------------------------
# MAIN DASHBOARD
# ------------------------------------------------

else:

    st.sidebar.success(f"{st.session_state.user_email}")
    st.sidebar.write(f"Role: {st.session_state.role}")
    st.sidebar.write(f"Plan: {st.session_state.plan}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    # Plan Logic
    if st.session_state.plan == "free":
        st.warning("Free Plan Active")
        if st.button("Upgrade to Pro"):
            st.info("Stripe integration will be added in Phase 4")

    else:
        st.success("Pro Plan Active 🔥")

    st.header("Dashboard Ready")

    st.info("Phase 1 complete: Auth + Role + Plan + OTP + UI foundation")
