import streamlit as st
import sqlite3
import hashlib
import google.generativeai as genai
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from PIL import Image
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# 🔧 CONFIGURATION & KEYS
# ==========================================
st.set_page_config(page_title="Safe-Ed Platform", page_icon="🏫", layout="wide")

# SECURE API KEY LOADING with fallback to Streamlit secrets
try:
    # Try environment variable first
    API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Fallback to Streamlit secrets if available
    if not API_KEY and hasattr(st, "secrets"):
        API_KEY = st.secrets.get("GEMINI_API_KEY", None)
    
    if not API_KEY:
        st.error("⚠️ API Key not found! Please set GEMINI_API_KEY in .env file")
        st.stop()
    
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"Configuration error: {str(e)}")
    st.stop()

# Use correct model name
MODEL_NAME = 'gemini-1.5-flash'

# ==========================================
# 🛢️ DATABASE & SECURITY LAYER
# ==========================================
DB_NAME = os.getenv("DB_NAME", "school.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores 
                 (username TEXT, topic TEXT, score INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes 
                 (username TEXT PRIMARY KEY, content TEXT)''')
    conn.commit()
    conn.close()

def make_hashes(password):
    # Keep salt consistent so logins don't break
    salted = password + "safeed_salt"
    return hashlib.sha256(salted.encode()).hexdigest()

def check_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username =? AND password =?', (username, make_hashes(password)))
    data = c.fetchall()
    conn.close()
    return data

def add_user(username, password, role, name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username,password,role,name) VALUES (?,?,?,?)', 
                  (username, make_hashes(password), role, name))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False 
    except Exception:
        result = False
    finally:
        conn.close()
    return result

def save_score(username, topic, score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO scores(username,topic,score,date) VALUES (?,?,?,?)', 
              (username, topic, score, str(datetime.now())[:10]))
    conn.commit()
    conn.close()

def get_stats(username):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT topic, score, date FROM scores WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

def save_note(username, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO notes(username, content) VALUES (?,?)', (username, content))
    conn.commit()
    conn.close()

def get_note(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT content FROM notes WHERE username=?', (username,))
    data = c.fetchone()
    conn.close()
    return data[0] if data else ""

init_db()

# ==========================================
# 🧠 AI ENGINE
# ==========================================
def run_ai(prompt):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: Unable to generate content. Please try again."

def create_pdf(header, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, header, 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    safe_text = content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, safe_text)
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# UI & NAVIGATION
# ==========================================
st.markdown("""
<style>
    .paper-box { background-color: white; color: black !important; padding: 25px; border-radius: 5px; 
                 box-shadow: 0 4px 8px rgba(0,0,0,0.1); font-family: 'Georgia'; border-left: 6px solid #2e7d32; }
    [data-testid="stSidebar"] { background-color: #000000; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if "explanation" not in st.session_state:
    st.session_state["explanation"] = None

# --- SCENE 1: LOGIN ---
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1,1])
    with col1:
        st.title("🛡️ Safe-Ed Portal")
        t1, t2 = st.tabs(["🔑 Login", "📝 Sign Up"])
        with t1:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Login"):
                res = check_user(u, p)
                if res:
                    st.session_state.update({"logged_in": True, "username": u, "role": res[0][2], "name": res[0][3]})
                    st.rerun()
        with t2:
            nu = st.text_input("New Username")
            np = st.text_input("New Password", type="password")
            nn = st.text_input("Full Name")
            nr = st.selectbox("Role", ["Student", "Teacher"])
            if st.button("Create"):
                if add_user(nu, np, nr, nn): st.success("Created!")
    with col2:
        st.info("Teacher: admin / admin")

# --- SCENE 2: DASHBOARD ---
else:
    with st.sidebar:
        st.title(st.session_state['name'])
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    if st.session_state['role'] == "Teacher":
        menu = st.sidebar.radio("Nav", ["🔬 Research", "📝 Tests", "📒 Notes"])
        if menu == "🔬 Research":
            topic = st.text_input("Topic")
            if st.button("Generate"):
                res = run_ai(f"Lesson plan for {topic}")
                st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
        elif menu == "📒 Notes":
            note = st.text_area("Log", value=get_note(st.session_state['username']))
            if st.button("Save"): save_note(st.session_state['username'], note)

    elif st.session_state['role'] == "Student":
        menu = st.sidebar.radio("Nav", ["📚 Learning", "🧠 Quiz", "📊 Stats"])
        
        if menu == "📚 Learning":
            topic = st.text_input("Topic")
            grade = st.selectbox("Grade", ["Grade 1-5", "Grade 6-8", "Grade 9-12"])
            if st.button("Explain"):
                res = run_ai(f"Explain {topic} to {grade} student.")
                st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)

        elif menu == "🧠 Quiz":
            topic = st.text_input("Quiz Topic")
            if st.button("Start"):
                res = run_ai(f"5 MCQs on {topic}")
                st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
            s = st.slider("Score", 0, 100)
            if st.button("Save Score"): save_score(st.session_state['username'], topic, s)

        elif menu == "📊 Stats":
            st.header("📊 My Progress")
            df = get_stats(st.session_state['username'])
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                st.bar_chart(df.set_index('topic')['score'])
                
                # NOVELTY: Weak Topic Analysis
                avg = df.groupby("topic")["score"].mean()
                weak = avg[avg < 60]
                if not weak.empty:
                    st.warning(f"Needs improvement: {', '.join(weak.index)}")
                    if st.button("Revise Weak Topics"):
                        st.session_state["explanation"] = run_ai(f"Simplify {weak.index[0]} for me.")
                
                if st.session_state["explanation"]:
                    st.markdown(f'<div class="paper-box">{st.session_state["explanation"]}</div>', unsafe_allow_html=True)