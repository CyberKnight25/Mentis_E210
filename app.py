import streamlit as st
import sqlite3
import hashlib
import google.generativeai as genai
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from PIL import Image

# ==========================================
#  CONFIGURATION & KEYS
# ==========================================
st.set_page_config(page_title="Safe-Ed Platform", page_icon="🏫", layout="wide")

# HARDCODED KEY (Keep this safe!)

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

MODEL_NAME = 'models/gemini-2.5-flash-lite'

# ==========================================
#  DATABASE & SECURITY LAYER
# ==========================================
def init_db():
    conn = sqlite3.connect('school.db')
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
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_user(username, password):
    conn = sqlite3.connect('school.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username =? AND password =?', (username, make_hashes(password)))
    data = c.fetchall()
    conn.close()
    return data

def add_user(username, password, role, name):
    conn = sqlite3.connect('school.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username,password,role,name) VALUES (?,?,?,?)', 
                  (username, make_hashes(password), role, name))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False 
    except:
        result = False
    finally:
        conn.close()
    return result

def save_score(username, topic, score):
    conn = sqlite3.connect('school.db')
    c = conn.cursor()
    c.execute('INSERT INTO scores(username,topic,score,date) VALUES (?,?,?,?)', 
              (username, topic, score, str(datetime.now())[:10]))
    conn.commit()
    conn.close()

def get_stats(username):
    conn = sqlite3.connect('school.db')
    df = pd.read_sql_query(f"SELECT topic, score, date FROM scores WHERE username='{username}'", conn)
    conn.close()
    return df

def save_note(username, content):
    conn = sqlite3.connect('school.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO notes(username, content) VALUES (?,?)', (username, content))
    conn.commit()
    conn.close()

def get_note(username):
    conn = sqlite3.connect('school.db')
    c = conn.cursor()
    c.execute('SELECT content FROM notes WHERE username=?', (username,))
    data = c.fetchone()
    conn.close()
    return data[0] if data else ""

# Initialize DB & Default Users
init_db()
add_user("admin", "admin", "Teacher", "Prof. X")
add_user("student", "student", "Student", "Miles Morales")
add_user("Hitesh", "hitu07", "Student", "Gayboy")

# ==========================================
#  AI ENGINE
# ==========================================
def run_ai(prompt):
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

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
    .paper-box { 
        background-color: white; 
        color: black !important; 
        padding: 25px; 
        border-radius: 5px; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.1); 
        font-family: 'Georgia'; 
        border-left: 6px solid #2e7d32; 
    }
    [data-testid="stSidebar"] { background-color: #000000; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stRadio > div[role="radiogroup"] > label { color: white !important; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- SCENE 1: LOGIN & SIGN UP ---
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1,1])
    
    with col1:
        st.title("🛡️ Safe-Ed Portal")
        tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Sign Up"])

        # === LOGIN TAB ===
        with tab_login:
            user = st.text_input("Username", key="login_user")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Login", key="btn_login"):
                res = check_user(user, pwd)
                if res:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user
                    st.session_state['role'] = res[0][2]
                    st.session_state['name'] = res[0][3]
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")

        # === SIGN UP TAB ===
        with tab_signup:
            st.caption("Create a new account instantly")
            new_user = st.text_input("Choose Username", key="new_user")
            new_pwd = st.text_input("Choose Password", type="password", key="new_pwd")
            new_name = st.text_input("Your Display Name", key="new_name")
            new_role = st.selectbox("Role", ["Student", "Teacher"], key="new_role")

            if st.button("Create Account", key="btn_signup"):
                if new_user and new_pwd and new_name:
                    if add_user(new_user, new_pwd, new_role, new_name):
                        st.success(f"Success! Account created for {new_name}.")
                        st.balloons()
                        st.info("Please switch to the 'Login' tab to sign in.")
                    else:
                        st.error("⚠️ Username already taken.")
                else:
                    st.warning("Please fill all fields.")

    with col2:
        st.info("System Status: Online 🟢")
        st.write("---")
        st.markdown("**Test Credentials:**")
        st.code("Teacher: admin / admin")
        st.code("Student: student / student")

# --- SCENE 2: DASHBOARD ---
else:
    with st.sidebar:
        st.title(f"{st.session_state['name']}")
        st.caption(f"Role: {st.session_state['role']}")
        st.divider()

    # TEACHER MODE
    if st.session_state['role'] == "Teacher":
        menu = st.sidebar.radio("Navigation", ["🔬 Research", "📝 Tests", "📝 Class Notes", "📒 Private Notes"])
        
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

        match menu:
            case "🔬 Research":
                st.header("🔬 Deep Lesson Research")
                col1, col2 = st.columns([3, 1])
                with col1: topic = st.text_input("Topic", "Thermodynamics")
                with col2: grade = st.selectbox("Grade Level", ["Grade 1-5", "Grade 6-8", "Grade 9-10", "High School", "University"])

                if st.button("Generate Plan"):
                    with st.spinner(f"Researching for {grade}..."):
                        prompt = f"Act as an expert teacher. Create a 5E Lesson Plan for {topic} ({grade})."
                        res = run_ai(prompt)
                        st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
                        st.download_button("Download PDF", create_pdf(f"Lesson: {topic}", res), "lesson.pdf")

            case "📝 Tests":
                st.header("📝 Exam Creator")
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                with col1: topic = st.text_input("Exam Topic", "History of AI")
                with col2: grade = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
                with col3: mcqs = st.text_input("MCQs","5")
                with col4: sa = st.text_input("Short Ans","2")
                with col5: la = st.text_input("Long Ans","1")

                if st.button("Generate Exam"):
                    with st.spinner("Drafting..."):
                        prompt = f"Create a final exam for {topic} ({grade}). {mcqs} MCQs, {sa} Short, {la} Essay. Include Answer Key."
                        res = run_ai(prompt)
                        st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
                        st.download_button("Download PDF", create_pdf(f"Exam: {topic}", res), "exam.pdf")

            case "📝 Class Notes":
                st.header("📝 Handouts")
                topic = st.text_input("Topic", "Newton's Laws")
                if st.button("Generate"):
                    res = run_ai(f"Create study notes on {topic}. Use bullet points and bold text.")
                    st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
                    st.download_button("Download PDF", create_pdf(f"Notes: {topic}", res), "notes.pdf")

            case "📒 Private Notes":
                st.header("📒 Scratchpad")
                current_note = get_note(st.session_state['username'])
                new_note = st.text_area("Teacher's Log", value=current_note, height=300)
                if st.button("💾 Save to Database"):
                    save_note(st.session_state['username'], new_note)
                    st.success("Note saved successfully!")

    # STUDENT MODE
    elif st.session_state['role'] == "Student":
        # Updated Menu List
        menu = st.sidebar.radio("Navigation", ["📚 Learning", "🧠 Quiz", "📊 Stats", "Visual Tutor"])
        
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

        match menu:
            case "📚 Learning":
                st.header("📚 AI Tutor")
                col1, col2 = st.columns([3, 1])
                with col1: topic = st.text_input("Topic", "Newton's Laws")
                with col2: grade = st.selectbox("Grade", ["Grade 1-5", "Grade 6-8", "Grade 9-12"])
                
                if st.button("Explain to me"):
                    with st.spinner("Teaching..."):
                        prompt = f"Explain {topic} to a student of {grade} simply. Use analogies."
                        res = run_ai(prompt)
                        st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)

            case "🧠 Quiz":
                st.header("🧠 Knowledge Check")
                col1, col2 = st.columns([3, 1])
                with col1: topic = st.text_input("Topic", "Newton's Laws")
                with col2: num = st.text_input("Num Questions", "5")
                
                if st.button("Generate Quiz"):
                    with st.spinner("Generating..."):
                        res = run_ai(f"Create {num} MCQ questions on {topic}. Show answers at the end.")
                        st.markdown(f'<div class="paper-box">{res}</div>', unsafe_allow_html=True)
                
                st.divider()
                col1, col2 = st.columns(2)
                score = col1.slider("My Score", 0, 100, 80)
                if col2.button("💾 Save Stats"):
                    save_score(st.session_state['username'], topic, score)
                    st.success("Saved!")

            case "📊 Stats":
                st.header("📊 My Progress")
                df = get_stats(st.session_state['username'])
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    st.bar_chart(df.set_index('topic')['score'])
                else:
                    st.info("No stats yet.")

            case "Visual Tutor":
                st.header("📸 Visual AI Tutor")
                st.caption("Snap a picture of a diagram, math problem, or paragraph.")

                
                input_method = st.radio("Input Method", ["Type", "Camera"], horizontal=True)

                prompt = ""
                image_data = None

                if input_method == "Type":
                    prompt = st.text_input("What are we learning?")
            
                elif input_method == "Camera":
                    img_file = st.camera_input("Take a picture")
                    if img_file:
                        image_data = Image.open(img_file)
                        st.image(image_data, caption="Captured", width=300)
                        prompt = st.text_input("Add a question (optional):", "Explain this")

                
                if st.button("Explain Visual"):
                    if prompt or image_data:
                        with st.spinner("Analyzing..."):
                            model = genai.GenerativeModel(MODEL_NAME)
                            if image_data:
                                response = model.generate_content([prompt, image_data])
                            else:
                                response = model.generate_content(prompt)
                            st.markdown(f'<div class="paper-box">{response.text}</div>', unsafe_allow_html=True)
                    else:
                        st.warning("Please provide text or an image.")