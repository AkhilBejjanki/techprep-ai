from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_cors import CORS
import os
from dotenv import load_dotenv
from groq import Groq
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from authlib.integrations.flask_client import OAuth
import psycopg
from psycopg.rows import dict_row  
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Configure Groq client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
CORS(app)

# PostgreSQL Database URL
DATABASE_URL = os.getenv('DATABASE_URL')

# Configure OAuth for Google
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Database connection
def get_db():
    conn = psycopg.connect(DATABASE_URL)
    return conn

# Database initialization
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        google_id TEXT UNIQUE,
        email TEXT,
        name TEXT,
        picture TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Chat history table
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        question TEXT,
        answer TEXT,
        code TEXT,
        language TEXT,
        mode TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
try:
    init_db()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"⚠️ Database initialization error: {str(e)}")

# Database helper functions
def get_or_create_user(google_id, email, name, picture):
    conn = get_db()
    c = conn.cursor(row_factory=dict_row)
    
    # Check if user exists
    c.execute('SELECT * FROM users WHERE google_id = %s', (google_id,))
    user = c.fetchone()
    
    if user is None:
        # Create new user
        c.execute('INSERT INTO users (google_id, email, name, picture) VALUES (%s, %s, %s, %s) RETURNING id',
                  (google_id, email, name, picture))
        user_id = c.fetchone()['id']
        conn.commit()
    else:
        user_id = user['id']
        # Update user info
        c.execute('UPDATE users SET email = %s, name = %s, picture = %s WHERE id = %s',
                  (email, name, picture, user_id))
        conn.commit()
    
    conn.close()
    return user_id

def save_chat_history(user_id, question, answer, code, language, mode):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO chat_history 
                 (user_id, question, answer, code, language, mode) 
                 VALUES (%s, %s, %s, %s, %s, %s)''',
              (user_id, question, answer, code, language, mode))
    conn.commit()
    conn.close()

def get_user_history(user_id, limit=50):
    conn = get_db()
    c = conn.cursor(row_factory=dict_row)
    c.execute('''SELECT * FROM chat_history 
                 WHERE user_id = %s 
                 ORDER BY created_at DESC 
                 LIMIT %s''', (user_id, limit))
    history = c.fetchall()
    conn.close()
    return [dict(row) for row in history]

# Authentication routes
@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if user_info:
            # Store user in database
            user_id = get_or_create_user(
                user_info['sub'],
                user_info['email'],
                user_info.get('name', ''),
                user_info.get('picture', '')
            )
            
            # Store in session
            session['user_id'] = user_id
            session['user_email'] = user_info['email']
            session['user_name'] = user_info.get('name', '')
            session['user_picture'] = user_info.get('picture', '')
            
        return redirect('/')
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/user')
def get_user():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user_id': session['user_id'],
            'email': session['user_email'],
            'name': session['user_name'],
            'picture': session['user_picture']
        })
    return jsonify({'logged_in': False})

# Topic classification keywords
PROGRAMMING_KEYWORDS = [
    'python', 'java', 'sql', 'javascript', 'html', 'css', 'loop', 'function',
    'array', 'list', 'dictionary', 'api', 'flask', 'django', 'class', 'object',
    'algorithm', 'dsa', 'frontend', 'backend', 'code', 'programming', 'variable',
    'syntax', 'method', 'inheritance', 'polymorphism', 'data structure'
]

THEORY_KEYWORDS = [
    'operating system', 'os', 'process', 'thread', 'deadlock', 'scheduling',
    'networking', 'tcp', 'udp', 'osi', 'sdlc', 'agile', 'cloud', 'devops',
    'aws', 'azure', 'gcp', 'testing', 'qa', 'scrum', 'waterfall', 'cicd'
]

def classify_topic(question):
    """Classify if question is programming or theory based"""
    question_lower = question.lower()
    
    for keyword in PROGRAMMING_KEYWORDS:
        if keyword in question_lower:
            return 'programming'
    
    for keyword in THEORY_KEYWORDS:
        if keyword in question_lower:
            return 'theory'
    
    return 'theory'

def detect_programming_language(question):
    """Detect the programming language from the question"""
    question_lower = question.lower()
    
    if 'python' in question_lower:
        return 'python'
    elif 'java' in question_lower:
        return 'java'
    elif 'sql' in question_lower:
        return 'sql'
    elif 'javascript' in question_lower or 'js' in question_lower:
        return 'javascript'
    
    return 'python'

def call_ai_api(prompt):
    """Call Groq API for AI responses - SUPER FAST!"""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a technical interview assistant. You MUST always respond with EXACTLY 7 numbered points. Never add introductions, conclusions, or extra text. Only return the numbered list from 1 to 7."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            max_tokens=1024,
        )
        
        return {
            "success": True,
            "response": chat_completion.choices[0].message.content
        }
    except Exception as e:
        print(f"API Error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_code_example_from_ai(language, topic, mode):
    """Generate code examples using Groq AI based on topic and mode"""
    
    if mode == 'beginner':
        prompt = f"""Generate a very simple, beginner-friendly {language} code example for: {topic}

Requirements:
- Keep it under 10 lines
- Use basic syntax only
- Add helpful comments
- Make it easy to understand
- No advanced concepts

Return ONLY the code, no explanations."""
    else:
        prompt = f"""Generate an advanced, professional {language} code example for: {topic}

Requirements:
- Show best practices
- Include error handling if relevant
- Use proper design patterns
- Keep it under 20 lines but showcase expertise
- Add minimal but useful comments

Return ONLY the code, no explanations."""
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            max_tokens=512,
        )
        
        code = chat_completion.choices[0].message.content.strip()
        
        if code.startswith('```'):
            lines = code.split('\n')
            code = '\n'.join(lines[1:-1]) if len(lines) > 2 else code
            code = code.strip()
        
        return code
    except Exception as e:
        print(f"Error generating code: {str(e)}")
        return get_fallback_code(language, mode)

def get_fallback_code(language, mode):
    """Fallback code examples if AI generation fails"""
    
    if mode == 'beginner':
        examples = {
            'python': '''# Basic Python example
x = 10
y = 20
result = x + y
print(result)''',
            
            'java': '''// Basic Java example
public class Main {
    public static void main(String[] args) {
        int x = 10;
        System.out.println(x);
    }
}''',
            
            'sql': '''-- Basic SQL query
SELECT * FROM users
WHERE age > 18;'''
        }
    else:
        examples = {
            'python': '''# Advanced Python example
def calculate_fibonacci(n):
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[-1] + fib[-2])
    return fib[:n]

print(calculate_fibonacci(10))''',
            
            'java': '''// Advanced Java example
public class DataProcessor {
    public List<String> process(List<String> data) {
        return data.stream()
            .filter(s -> !s.isEmpty())
            .map(String::toUpperCase)
            .collect(Collectors.toList());
    }
}''',
            
            'sql': '''-- Advanced SQL query
SELECT d.department_name, 
       AVG(e.salary) as avg_salary,
       COUNT(*) as employee_count
FROM employees e
JOIN departments d ON e.dept_id = d.id
GROUP BY d.department_name
HAVING AVG(e.salary) > 50000;'''
        }
    
    return examples.get(language, examples['python'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        mode = data.get('mode', 'beginner')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        topic_type = classify_topic(question)
        language = detect_programming_language(question) if topic_type == 'programming' else None
        
        if mode == 'beginner':
            prompt = f"""Answer this question in EXACTLY 7 simple numbered points for beginners.
Each point should be short, clear, and easy to understand.
Use simple words. No technical jargon.

Question: {question}

IMPORTANT: You MUST return EXACTLY 7 points in this format:
1. [First simple point]
2. [Second simple point]
3. [Third simple point]
4. [Fourth simple point]
5. [Fifth simple point]
6. [Sixth simple point]
7. [Seventh simple point]

Return ONLY the numbered list. No introduction, no conclusion, no extra text."""
        else:
            prompt = f"""Answer this question in EXACTLY 7 detailed technical numbered points.
Each point should be precise, technical, and professional.
Include important concepts, best practices, and technical details.

Question: {question}

IMPORTANT: You MUST return EXACTLY 7 points in this format:
1. [First technical point]
2. [Second technical point]
3. [Third technical point]
4. [Fourth technical point]
5. [Fifth technical point]
6. [Sixth technical point]
7. [Seventh technical point]

Return ONLY the numbered list. No introduction, no conclusion, no extra text."""
        
        ai_result = call_ai_api(prompt)
        
        if not ai_result.get('success'):
            return jsonify({'error': 'AI service error'}), 500
        
        response_text = ai_result.get('response', '').strip()
        
        lines = response_text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or (len(line) > 1 and line[0:2].replace('.', '').isdigit())):
                cleaned_lines.append(line)
        
        if len(cleaned_lines) < 7:
            response_text = '\n'.join(cleaned_lines)
        else:
            response_text = '\n'.join(cleaned_lines[:7])
        
        code_example = None
        if topic_type == 'programming' and language:
            code_example = get_code_example_from_ai(language, question, mode)
        
        # Save to history if user is logged in
        if 'user_id' in session:
            save_chat_history(
                session['user_id'],
                question,
                response_text,
                code_example,
                language,
                mode
            )
        
        return jsonify({
            'success': True,
            'answer': response_text,
            'code': code_example,
            'language': language,
            'topic_type': topic_type,
            'mode': mode
        })
        
    except Exception as e:
        print(f"Error in ask_question: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    history = get_user_history(session['user_id'])
    return jsonify({'history': history})

@app.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history(history_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM chat_history WHERE id = %s AND user_id = %s',
              (history_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM chat_history WHERE user_id = %s', (session['user_id'],))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    try:
        data = request.get_json()
        question = data.get('question', 'Question')
        answer = data.get('answer', '')
        code = data.get('code', '')
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor='#1a1a1a',
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph("TechPrep AI - Technical Interview Answer", title_style))
        story.append(Spacer(1, 12))
        
        # Question Section
        question_style = ParagraphStyle(
            'QuestionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#000000',
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph("Question:", question_style))
        
        question_text_style = ParagraphStyle(
            'QuestionText',
            parent=styles['Normal'],
            fontSize=11,
            leftIndent=12,
            spaceAfter=16
        )
        story.append(Paragraph(question, question_text_style))
        
        # Answer Section
        story.append(Paragraph("Answer:", question_style))
        
        # Format answer points
        answer_lines = answer.split('\n')
        for line in answer_lines:
            if line.strip():
                answer_style = ParagraphStyle(
                    'AnswerPoint',
                    parent=styles['Normal'],
                    fontSize=11,
                    leftIndent=12,
                    spaceAfter=8
                )
                story.append(Paragraph(line, answer_style))
        
        # Code example if present
        if code:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Code Example:", question_style))
            
            code_style = ParagraphStyle(
                'Code',
                parent=styles['Normal'],
                fontSize=9,
                leftIndent=12,
                fontName='Courier',
                spaceAfter=12,
                textColor='#333333'
            )
            # Format code with line breaks preserved
            code_html = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"<pre>{code_html}</pre>", code_style))
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='techprep_answer.pdf'
        )
        
    except Exception as e:
        print(f"Error exporting PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)