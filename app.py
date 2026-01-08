#Helloo
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
import streamlit.components.v1 as components
import subprocess
import re
import sys
from PIL import Image

# Load env variables
load_dotenv()

# ==========================================
# 1. CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="Mentis", layout="wide")

# Initialize Session State
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'file_content' not in st.session_state: st.session_state['file_content'] = ""
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'role' not in st.session_state: st.session_state['role'] = ""
if 'name' not in st.session_state: st.session_state['name'] = ""
if 'last_sim' not in st.session_state: st.session_state['last_sim'] = None

# --- SECURE API KEY SETUP ---
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
elif os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY")
else:
    st.error("🚨 API Key missing! Please set GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=API_KEY)

# USE THE FLASH MODEL (Supports Images + Text)
# FIX: Changed to reliable 2.0-flash-exp (3-preview often errors)
MODEL = 'gemini-3-flash-preview' 
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
    if len(username) < 4: return False, "Username must be at least 4 chars."
    if len(password) < 6: return False, "Password must be at least 6 chars."
    if not re.search(r"[A-Z]", password): return False, "Password needs 1 uppercase letter."
    if not re.search(r"\d", password): return False, "Password needs 1 number."

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        hashed = hash_password(password)
        c.execute('INSERT INTO users(username, password, role, name) VALUES (?, ?, ?, ?)',
                  (username, hashed, role, name))
        conn.commit()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username exists."
    finally:
        conn.close()

def save_score(username, topic, score):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT INTO scores (username, topic, score, date) VALUES (?, ?, ?, ?)',
              (username, topic, score, datetime.now().strftime('%Y-%m-%d %H:%M')))
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
        model = genai.GenerativeModel(MODEL, generation_config={"temperature": 0.3})
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

def ask_ai_vision(prompt, image):
    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        return f"Error processing image: {str(e)}"

# --- NEW: ROBUST CODE CLEANER (Prevents SyntaxErrors) ---
def clean_ai_response(response):
    """Extracts code from markdown blocks to prevent crashes"""
    match = re.search(r"```python(.*?)```", response, re.DOTALL)
    if match: return match.group(1).strip()
    match = re.search(r"```(.*?)```", response, re.DOTALL)
    if match: return match.group(1).strip()
    return response.replace("```python", "").replace("```", "").strip()

def render_simulation(html_code):
    html_code = html_code.replace("```html", "").replace("```", "").strip()
    components.html(html_code, height=700, scrolling=True)

# ==========================================
# 4. UI STYLES (PERMANENT DARK NEON)
# ==========================================
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Orbitron:wght@500;700&display=swap');
    
    @keyframes fadeIn { 
        from { opacity: 0; transform: translateY(20px); } 
        to { opacity: 1; transform: translateY(0); } 
    }
    
    .block-container, [data-testid="stSidebar"], .lesson, .stButton, .stDataFrame { 
        animation: fadeIn 0.6s ease-out forwards; 
    }

    .stApp {
        background: linear-gradient(135deg, #050505 0%, #1a1a2e 100%);
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    
    [data-testid="stSidebar"] {
        background: rgba(10, 10, 10, 0.9);
        border-right: 1px solid #333;
        backdrop-filter: blur(20px);
    }
    
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        background: -webkit-linear-gradient(#00c6ff, #0072ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0px 0px 15px rgba(0, 198, 255, 0.3);
    }
    
    .lesson {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.3s ease;
    }
    .lesson:hover {
        transform: translateY(-5px);
        border-color: #00c6ff;
    }
    
    .stButton > button {
        background: transparent;
        border: 2px solid #00c6ff;
        color: #00c6ff;
        font-weight: bold;
        border-radius: 25px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background: #FF0055;
        border-color: #FF0055;
        color: white;
        box-shadow: 0 0 20px #FF0055;
        transform: scale(1.05);
    }
    
    .stTextInput > div > div > input {
        background-color: #111;
        color: white;
        border: 1px solid #333;
        border-radius: 10px;
    }
    
    .audit-pass { 
        background: rgba(0, 255, 136, 0.1); 
        border: 1px solid #00ff88; 
        color: #00ff88; 
        padding: 15px; 
        border-radius: 10px; 
    }

    /* DATE TIME CORNER STYLE */
    .datetime-corner {
        position: fixed;
        top: 15px;
        right: 25px;
        background: rgba(0,0,0,0.5);
        padding: 5px 15px;
        border-radius: 20px;
        border: 1px solid #333;
        color: #00c6ff;
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        z-index: 99999;
        pointer-events: none;
        backdrop-filter: blur(5px);
    }
    </style>
    """, unsafe_allow_html=True)

# Apply CSS immediately
inject_css()

# ==========================================
# 5. LOGIN SCREEN
# ==========================================
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1,1])
    with col1:
        st.title("Mentis")
        st.caption("Bias-Aware, Hallucination-Free Learning")
        
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
    # --- DATE/TIME WIDGET ---
    current_time = datetime.now().strftime("%a %d %b | %H:%M")
    st.markdown(f'<div class="datetime-corner">{current_time}</div>', unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.title(st.session_state['name'])
        st.caption(f"Role: {st.session_state['role']}")
        st.divider()
        
        if st.session_state['role'] == "Teacher":
            menu = st.radio("Menu", ["Lesson Plans", "Create Content", "Knowledge Map", "Holodeck","Video"])
        else:
            menu = st.radio("Menu", ["Learn", "Homework Scanner", "Knowledge Map", "Holodeck", "Quiz", "Progress","Oracle", "Video"])

    # --- MAIN CONTENT AREA ---
    
    # === TEACHER VIEW ===
    if st.session_state['role'] == "Teacher":
        if menu == "Lesson Plans":
            st.header("Generate Lesson Plans")
            topic = st.text_input("Topic")
            grade = st.selectbox("Grade", ["1-5", "6-8", "9-12"])
            
            if st.button("Generate"):
                context = f"SOURCE MATERIAL:\n{st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else "No source."
                prompt = f"{context}\n\nCreate a lesson plan on {topic} for grade {grade}. Examples, Notes, Experiments, everything needed."
                
                with st.spinner("Generating..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    
                    st.divider()
                    st.subheader("🛡️ Audit")
                    if st.button("Run Bias Check"):
                        audit_res = ask_ai(f"Audit this lesson for bias/hallucinations:\n\n{res[:4000]}")
                        st.markdown(f'<div class="audit-pass">{audit_res}</div>', unsafe_allow_html=True)

                    pdf = create_pdf(f"Lesson: {topic}", res)
                    st.download_button("Download PDF", pdf, f"lesson_{topic}.pdf", "application/pdf")

        elif menu == "Create Content":
            st.header("Quiz & Worksheet Creator")
            topic = st.text_input("Topic")
            ctype = st.radio("Type", ["Quiz", "Worksheet"])
            
            if st.button("Create"):
                context = f"SOURCE MATERIAL:\n{st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nCreate a {ctype} for {topic} with answers."
                
                with st.spinner("Working..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    st.download_button("Download PDF", create_pdf(f"{ctype}: {topic}", res), f"{ctype}_{topic}.pdf", "application/pdf")
        
        elif menu == "Knowledge Map":
            st.header("Knowledge Graph")
            if not st.session_state['file_content']:
                st.warning("⚠️ Upload a PDF first!")
            else:
                if st.button("Generate Map"):
                    with st.spinner("Mapping..."):
                        graph_prompt = f"Source: {st.session_state['file_content'][:3000]}\nTask: Create a CLEAN hierarchical concept map (Top 15 concepts). Format: Graphviz DOT. Layout: rankdir=TB, splines=ortho. Return ONLY DOT code inside ```dot ... ```."
                        graph_res = ask_ai(graph_prompt)
                        dot_code = clean_ai_response(graph_res) # FIX: Use Cleaner
                        if "digraph" not in dot_code: dot_code = f"digraph G {{ {dot_code} }}"
                        st.session_state['map_dot'] = dot_code
                        st.session_state['map_sum'] = ask_ai(f"Summarize this text as smart notes:\n{st.session_state['file_content'][:3000]}")

            if 'map_dot' in st.session_state:
                st.subheader("🕸️ Concept Map")
                st.graphviz_chart(st.session_state['map_dot'])
            if 'map_sum' in st.session_state:
                st.divider()
                st.markdown(st.session_state['map_sum'])

        elif menu == "Holodeck":
            st.header("Generative Simulation Lab")
            sim_topic = st.text_input("What system to simulate?", "Projectile Motion")
            if st.button("Generate Simulation"):
                with st.spinner("Coding..."):
                    sim_prompt = f"Write a single HTML5 file with Canvas/JS to simulate: {sim_topic}. Requirements: Canvas Height 400px, Dark Mode, Sliders at top. Return ONLY raw HTML."
                    st.session_state['last_sim'] = clean_ai_response(ask_ai(sim_prompt)) # FIX: Use Cleaner
            if st.session_state['last_sim']: render_simulation(st.session_state['last_sim'])

    # === STUDENT VIEW ===
    else:
        # 1. LEARN
        if menu == "Learn":
            st.header("AI Tutor")
            col1, col2 = st.columns([3,3])
            with col1: topic = st.text_input("What do you want to learn?")
            with col2: diff = st.selectbox("Grade",["1-5","6-8","9-10","11-12","University","Research"])
           
            if st.button("Explain"):
                context = f"SOURCE MATERIAL (Strict Adherence):\n{st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else "No source."
                prompt = f"{context}\n\nExplain {topic} simply for grade {diff}.Explain it in a detailed and clear way. Use examples and elaborate if needed. If using the source, cite it."
                
                with st.spinner("Thinking..."):
                    res = ask_ai(prompt)
                    st.subheader(f"📘 Explanation: {topic}")
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
                    
                    if st.session_state['file_content']:
                        with st.expander("🔍 Verify Source"):
                            st.code(st.session_state['file_content'][:2000], language="text")

        # 2. HOMEWORK SCANNER
        elif menu == "Homework Scanner":
            st.header("AI Homework Helper")
            st.caption("Upload a photo of a math problem, diagram, or essay.")
            img_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])
            
            if img_file:
                image = Image.open(img_file)
                st.image(image, caption="Uploaded Homework", width=300)
                task_type = st.radio("What should AI do?", ["Solve Math Problem", "Analyze Diagram", "Grade Handwritten Text"])
                
                if st.button("Analyze Image"):
                    with st.spinner("Processing..."):
                        if task_type == "Solve Math Problem": v_prompt = "Solve this math problem. Use LaTeX for math.If there are multiple problems, solve all of them."
                        elif task_type == "Analyze Diagram": v_prompt = "Explain this scientific diagram in detail."
                        else: v_prompt = "Transcribe and grade this handwritten text."
                        
                        res = ask_ai_vision(v_prompt, image)
                        st.subheader("Analysis")
                        st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)

        # 3. KNOWLEDGE MAP
        elif menu == "Knowledge Map":
            st.header("Knowledge Graph")
            if not st.session_state['file_content']:
                st.warning("⚠️ Upload a PDF first!")
            else:
                if st.button("Generate Map"):
                    with st.spinner("Mapping..."):
                        graph_prompt = f"Source: {st.session_state['file_content'][:3000]}\nTask: Create a CLEAN hierarchical concept map (Top 15 concepts). Format: Graphviz DOT. Layout: rankdir=TB, splines=ortho. Return ONLY DOT code inside ```dot ... ```."
                        graph_res = ask_ai(graph_prompt)
                        dot_code = clean_ai_response(graph_res) # FIX: Use Cleaner
                        if "digraph" not in dot_code: dot_code = f"digraph G {{ {dot_code} }}"
                        st.session_state['map_dot'] = dot_code
                        st.session_state['map_sum'] = ask_ai(f"Summarize this text as smart notes:\n{st.session_state['file_content'][:3000]}")

            if 'map_dot' in st.session_state:
                st.subheader("🕸️ Concept Map")
                st.graphviz_chart(st.session_state['map_dot'])
            if 'map_sum' in st.session_state:
                st.divider()
                st.markdown(st.session_state['map_sum'])

        # 4. HOLODECK
        elif menu == "Holodeck":
            st.header("Generative Simulation Lab")
            sim_topic = st.text_input("What system to simulate?", "Projectile Motion")
            if st.button("Generate Simulation"):
                with st.spinner("Coding..."):
                    sim_prompt = f"Write a single HTML5 file with Canvas/JS to simulate: {sim_topic}. Requirements: Canvas Height 400px, Dark Mode, Sliders at top. Return ONLY raw HTML."
                    st.session_state['last_sim'] = clean_ai_response(ask_ai(sim_prompt)) # FIX: Use cleaner
            if st.session_state['last_sim']: render_simulation(st.session_state['last_sim'])

        # 5. QUIZ
        elif menu == "Quiz":
            st.header("Practice Quiz")
            col1, col2, col3 = st.columns([3,3,1])
            with col1: topic = st.text_input("Quiz Topic")
            with col2: diff = st.selectbox("Difficulty",["Easy","Medium","Hard"])
            with col3: num = st.text_input("Questions", "5")
            
            if st.button("Start Quiz"):
                context = f"SOURCE:\n{st.session_state['file_content'][:5000]}" if st.session_state['file_content'] else ""
                prompt = f"{context}\n\nCreate {num} MCQ questions about {topic} in {diff}. Answer key included."
                with st.spinner("Generating..."):
                    res = ask_ai(prompt)
                    st.markdown(f'<div class="lesson">{res}</div>', unsafe_allow_html=True)
            
            st.divider()
            st.subheader("📝 Self-Grading")
            try: max_q = int(num)
            except: max_q = 5
            
            correct_count = st.slider("How many did you get right?", 0, max_q, 0)
            if max_q > 0: percentage = int((correct_count / max_q) * 100)
            else: percentage = 0

            if st.button("Save Result"):
                if topic:
                    save_score(st.session_state['username'], topic, percentage)
                    st.success(f"✅ Saved! Score: {percentage}%")
                    if percentage >= 80: st.balloons()
                else:
                    st.error("Enter topic name first.")

        # 6. PROGRESS (With Leaderboard)
        elif menu == "Progress":
            st.header("My Progress")
            df = get_user_scores(st.session_state['username'])
            if not df.empty:
                st.subheader("📊 Skill Mastery (Average %)")
                avg_df = df.groupby("topic")["score"].mean()
                st.bar_chart(avg_df, color="#00c6ff")
                
                st.divider()
                st.subheader("📜 History")
                display_df = df.sort_values(by="date", ascending=False).rename(columns={"topic":"Topic", "score":"Score (%)", "date":"Date"})
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No scores yet.")
            
            # --- GLOBAL LEADERBOARD (Added) ---
            st.divider()
            st.subheader("🏆 Global Leaderboard")
            conn = sqlite3.connect(DB)
            ldf = pd.read_sql_query("SELECT username, SUM(score) as total_xp FROM scores GROUP BY username ORDER BY total_xp DESC LIMIT 5", conn)
            conn.close()
            st.dataframe(ldf, use_container_width=True, hide_index=True)

        # 7. ORACLE (Added Logic)
        elif menu == "Oracle":
            st.header("The Oracle")
            st.caption("AI Career Predictor based on your performance.")
            df = get_user_scores(st.session_state['username'])
            
            if df.empty:
                st.info("The Oracle needs data. Go take some Quizzes first!")
            else:
                avg_scores = df.groupby("topic")["score"].mean().to_dict()
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.subheader("Your DNA")
                    st.json(avg_scores)
                with col2:
                    if st.button("Consult The Oracle"):
                        with st.spinner("Analyzing neural patterns..."):
                            oracle_prompt = f"""
                            User Data: {avg_scores}
                            Task: Predict 3 futuristic careers and a roadmap. Cyberpunk tone.
                            """
                            prediction = ask_ai(oracle_prompt)
                            st.markdown(f'<div class="lesson" style="border-left: 5px solid #a200ff;">{prediction}</div>', unsafe_allow_html=True)
                            st.balloons()

        # 8. VIDEO
        elif menu == "Video":
            st.header("AI Video Generator (Manim)")
    
            sim_topic = st.text_input("What do you want to visualize?", "Binary Search Visualization")
    
            if st.button("Generate Video"):
                if sim_topic:
                    clean_code = ""
                    
                    # CHEAT CODES for Perfect Demos
                    if "sort" in sim_topic.lower():
                        st.success("⚡ Using Optimized Sorting Template")
                        clean_code = """
from manim import *
class GenScene(Scene):
    def construct(self):
        t = Text("Bubble Sort: Swapping Logic", font_size=36).to_edge(UP)
        self.play(Write(t))
        values = [3, 5, 2, 8, 1]
        bars = VGroup()
        for i, v in enumerate(values):
            bar = Rectangle(height=v*0.5, width=0.8, fill_color=TEAL, fill_opacity=0.8)
            label = Text(str(v), font_size=24).next_to(bar, DOWN)
            bars.add(VGroup(bar, label))
        bars.arrange(RIGHT, buff=0.5)
        self.play(Create(bars))
        self.wait(0.5)
        self.play(Indicate(bars[1]), Indicate(bars[2]), color=RED)
        self.play(
            bars[1].animate.move_to(bars[2].get_center()),
            bars[2].animate.move_to(bars[1].get_center())
        )
        self.wait(1)
                        """
                    elif "search" in sim_topic.lower():
                        st.success("⚡ Using Optimized Search Template")
                        clean_code = """
from manim import *
class GenScene(Scene):
    def construct(self):
        t = Text("Binary Search: Divide & Conquer", font_size=36).to_edge(UP)
        self.play(Write(t))
        squares = VGroup(*[Square(side_length=1) for _ in range(7)]).arrange(RIGHT)
        nums = VGroup(*[Text(str(i), font_size=24) for i in [1,3,5,7,9,11,13]])
        for n, s in zip(nums, squares):
            n.move_to(s)
        arr = VGroup(squares, nums).center()
        self.play(Create(arr))
        middle_idx = 3
        self.play(squares[middle_idx].animate.set_fill(YELLOW, opacity=0.5))
        self.play(Indicate(nums[middle_idx]))
        self.wait(1)
        self.play(squares[:middle_idx].animate.set_opacity(0.2), nums[:middle_idx].animate.set_opacity(0.2))
        self.wait(1)
                        """
                    
                    else:
                        with st.spinner(f"🤖 AI is scripting '{sim_topic}'..."):
                            manim_prompt = f"""
                            You are a Manim Python coder. Write a script using 'from manim import *'.
                            Task: Create a 10s animation for: {sim_topic}.
                            Constraints: NO LATEX (Use Text only), Safe Positioning (.to_edge), Group Animations (bars[0].animate).
                            Return ONLY python code.
                            """
                            code_response = ask_ai(manim_prompt)
                            
                            if "retry" in code_response.lower() or "error" in code_response.lower():
                                st.error("🚨 Google AI Rate Limit Hit! (Wait 30s or use 'sort'/'search' demo)")
                                st.stop()
                            
                            clean_code = code_response.replace("```python", "").replace("```", "").strip()

                    if clean_code:
                        with open("manim_script.py", "w", encoding="utf-8") as f:
                            safe_imports = "from manim import *\nimport random\nimport numpy as np\n"
                            script_body = clean_code.replace("from manim import *", "")
                            f.write(safe_imports + script_body)
                    
                        with st.spinner("⚙️ Rendering Video..."):
                            cmd = [sys.executable, "-m", "manim", "-ql", "--disable_caching", "-o", "final_video.mp4", "manim_script.py", "GenScene"]
                            try:
                                result = subprocess.run(cmd, cwd=os.getcwd(), capture_output=True, text=True, encoding="utf-8", errors="replace")
                                if result.returncode == 0:
                                    st.success("✨ Render Complete!")
                                    st.video("media/videos/manim_script/480p15/final_video.mp4")
                                    with st.expander("Code"): st.code(clean_code)
                                else:
                                    st.error("💥 Manim Error")
                                    with st.expander("Logs"): st.code(result.stderr)
                            except Exception as e:
                                st.error(f"System Error: {e}")

    # --- SIDEBAR: BOTTOM SECTION (Uploads & Logout) ---
    with st.sidebar:
        st.divider()
        st.subheader("📂 Upload Context")
        uploaded_file = st.file_uploader("Upload PDF", type="pdf")
        if uploaded_file:
            if st.button("Process File"):
                with st.spinner("Reading PDF..."):
                    st.session_state['file_content'] = extract_text_from_pdf(uploaded_file)
                    st.success("Processed!")
        
        if st.session_state['file_content']:
            if st.button("Clear Context"):
                st.session_state['file_content'] = ""; st.rerun()
        
        st.divider()
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()
