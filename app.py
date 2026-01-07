import streamlit as st
import sqlite3
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv
import bcrypt
from fpdf import FPDF
import io
import PyPDF2

# Load env variables
load_dotenv()

# ==========================================
# 1. CONFIG & SESSION STATE (MUST BE FIRST)
# ==========================================
st.set_page_config(page_title="Safe-Ed", page_icon="🏫", layout="wide")

# Initialize Session State immediately to prevent KeyErrors
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'file_content' not in st.session_state:
    st.session_state['file_content'] = ""
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'role' not in st.session_state:
    st.session_state['role'] = ""
if 'name' not in st.session_state:
    st.session_state['name'] = ""

API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not API_KEY:
    # Hardcoded fallback for hackathon demo
    API_KEY = "AIzaSyC..." 

genai.configure(api_key=API_KEY)
MODEL = 'gemini-2.5-flash-lite'
DB = "school.db"

# ==========================================
# 2. DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores 
                 (username TEXT, topic TEXT, score INTEGER, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes 
                 (username TEXT PRIMARY KEY, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_user(username, password):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    if not user: return None
    try:
        if bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
            return user
    except: return None 
    return None

def register_user(username, password, role, name):
    if len(username) < 3: return False, "Username too short"
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        hashed = hash_password(password)
        c.execute('INSERT INTO users(username, password, role, name) VALUES (?, ?, ?, ?)',
                  (username, hashed, role, name))
        conn.commit()
        return True, "Account created"
    except sqlite3.IntegrityError:
        return False, "Username exists"
    finally:
        conn.close()

def save_score(username, topic, score):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT INTO scores (username, topic, score, date) VALUES (?, ?, ?, ?)',
              (username, topic, score, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def get_user_scores(username):
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT topic, score, date FROM scores WHERE username = ? ORDER BY date DESC", conn, params=(username,))
    conn.close()
    return df

def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def sanitize_for_pdf(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, title[:50], 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, sanitize_for_pdf(content))
    return pdf.output(dest='S').encode('latin-1')

def ask_ai(prompt):
    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# 4. UI STYLES
# ==========================================
st.markdown("""
<style>
    .lesson { background: #f0f2f6; color: black; padding: 20px; border-radius: 8px; border-left: 5px solid #2e7d32; }
    [data-testid="stSidebar"] { background: #111; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. LOGIN SCREEN
# ==========================================
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1,1])
    with col1:
        st.title("🛡️ Safe-Ed")
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login"):
                user = check_user(u, p)
                if user:
                    st.session_state.update({"logged_in": True, "username": u, "role": user[2], "name": user[3]})
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        with tab2:
            nu = st.text_input("New Username")
            np = st.text_input("New Password", type="password")
            nn = st.text_input("Full Name")
            nr = st.selectbox("Role", ["Student", "Teacher"])
            if st.button("Create Account"):
                success, msg = register_user(nu, np, nr, nn)
                if success: st.success(msg)
                else: st.error(msg)
    with col2:
        st.info("Demo: admin / admin")

# ==========================================
# 6. MAIN DASHBOARD
# ==========================================
else:
    with st.sidebar:
        st.title(st.session_state['name'])
        st.caption(st.session_state['role'])
        
        # --- FILE UPLOADER ---
        st.divider()
        st.subheader("📂 Upload Context")
        uploaded_file = st.file_uploader("Upload PDF (Textbook/Notes)", type="pdf")
        if uploaded_file:
            if st.button("Process File"):
                with st.spinner("Reading PDF..."):
                    text = extract_text_from_pdf(uploaded_file)
                    st.session_state['file_content'] = text
                    st.success("File processed! AI will now use this context.")
        
        # Safe Check for file content
        if st.session_state['file_content']:
            st.info("✅ Context Loaded")
            if st.button("Clear Context"):
                st.session_state['file_content'] = ""
                st.rerun()
        
        st.divider()
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    # TEACHER VIEW
    if st.session_state['role'] == "Teacher":
        menu = st.sidebar.radio("Menu", ["Lesson Plans", "Create Content"])
        
        if menu == "Lesson Plans":
            st.header("Generate Lesson Plans")
            topic = st.text_input("Topic")
            grade = st.selectbox("Grade", ["1-5", "6-8", "9-12"])
            
            if st.button("Generate"):
                context = f"Use this material as reference: {st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nCreate a lesson plan on {topic} for grade {grade}."
                
                with st.spinner("Generating..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    
                    pdf = create_pdf(f"Lesson: {topic}", res)
                    st.download_button("Download PDF", pdf, f"lesson_{topic}.pdf", "application/pdf")

        elif menu == "Create Content":
            st.header("Quiz & Worksheet Creator")
            topic = st.text_input("Topic")
            ctype = st.radio("Type", ["Quiz", "Worksheet"])
            
            if st.button("Create"):
                context = f"Base the questions on this text: {st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nCreate a {ctype} for {topic} with answers."
                
                with st.spinner("Working..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    st.download_button("Download PDF", create_pdf(f"{ctype}: {topic}", res), f"{ctype}_{topic}.pdf", "application/pdf")

    # STUDENT VIEW
    else:
        menu = st.sidebar.radio("Menu", ["Learn", "Quiz", "Progress"])
        
        if menu == "Learn":
            st.header("AI Tutor")
            col1, col2 = st.columns([3,3])
            with col1: topic = st.text_input("What do you want to learn?")
            with col2: diff = st.selectbox("Grade",["1-5","6-8","9-10","11-12","University","Research"])
           
            
            if st.button("Explain"):
                context = f"Explain using this source material: {st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nExplain {topic} simply."
                
                with st.spinner("Thinking..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    
                    # Graphviz Diagram Logic
                    diag_prompt = f"Create a Graphviz DOT code to visualize '{topic}'. Return ONLY the code inside 'digraph G {{ ... }}'."
                    try:
                        code = ask_ai(diag_prompt).replace("```dot", "").replace("```", "").strip()
                        if "digraph" not in code: code = f"digraph G {{ {code} }}"
                        st.graphviz_chart(code)
                    except: pass

        elif menu == "Quiz":
            st.header("Practice Quiz")
            col1, col2, col3 = st.columns([3,3,1])
            with col1: topic = st.text_input("What do you want to learn?")
            with col2: diff = st.selectbox("Difficulty",["Easy","Medium","Hard","AP","University","Research"])
            with col3: num= st.text_input("Number of questions","")
            
            if st.button("Start Quiz"):
                context = f"Create questions based ONLY on this text: {st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nCreate {num} MCQ questions about {topic} in {diff} with each question harder than the prev with answer key."
                
                with st.spinner("Generating..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
            
            st.divider()
            score = st.slider("Score", 0, {num})
            if st.button("Save Score"):
                save_score(st.session_state['username'], topic, score)
                st.success("Saved!")

        elif menu == "Progress":
            st.header("My Progress")
            df = get_user_scores(st.session_state['username'])
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                st.bar_chart(df.set_index('topic')['score'])
            else:
                st.info("No scores yet.")