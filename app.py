from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
from dotenv import load_dotenv
from groq import Groq
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# Load environment variables
load_dotenv()

# Configure Groq client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

app = Flask(__name__)
CORS(app)

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

def is_technical_question(question):
    """Check if question is strictly programming/technical related"""
    question_lower = question.lower()
    
    # Comprehensive programming and technical keywords
    technical_keywords = [
        'python', 'java', 'sql', 'javascript', 'html', 'css', 'loop', 'function',
        'array', 'list', 'dictionary', 'api', 'flask', 'django', 'class', 'object',
        'algorithm', 'dsa', 'frontend', 'backend', 'code', 'programming', 'variable',
        'syntax', 'method', 'inheritance', 'polymorphism', 'data structure',
        'operating system', 'os', 'process', 'thread', 'deadlock', 'scheduling',
        'networking', 'tcp', 'udp', 'osi', 'sdlc', 'agile', 'cloud', 'devops',
        'aws', 'azure', 'gcp', 'testing', 'qa', 'scrum', 'waterfall', 'cicd',
        'react', 'vue', 'angular', 'nodejs', 'express', 'mongodb', 'postgresql',
        'debug', 'compile', 'runtime', 'database', 'framework', 'library',
        'github', 'git', 'version control', 'deploy', 'container', 'docker',
        'kubernetes', 'microservice', 'rest', 'graphql', 'websocket', 'redis',
        'cache', 'server', 'client', 'http', 'request', 'response', 'json',
        'xml', 'api endpoint', 'middleware', 'authentication', 'authorization',
        'encryption', 'hash', 'regex', 'exception', 'error handling', 'logging',
        'performance', 'optimization', 'memory', 'cpu', 'latency', 'throughput',
        'scalability', 'availability', 'reliability', 'consistency', 'distributed',
        'parallel', 'concurrent', 'async', 'promise', 'callback', 'closure',
        'scope', 'prototype', 'recursion', 'tree', 'graph', 'queue', 'stack',
        'linked list', 'hash table', 'binary search', 'sorting', 'traversal',
        'dynamic programming', 'greedy', 'backtracking', 'brute force', 'divide conquer','oop'
    ]
    
    # Check if any technical keyword is in the question
    return any(keyword in question_lower for keyword in technical_keywords)

def get_rejection_reason(question):
    """Generate a helpful rejection message for non-technical questions"""
    return {
        'success': False,
        'error': 'This question is not programming or technical related. Please ask questions about: Python, Java, JavaScript, SQL, Algorithms, Data Structures, Cloud, DevOps, Networking, Databases, Frameworks (Django, React, etc.), or other programming/tech topics.',
        'category': 'non-technical'
    }

def classify_topic(question):
    """Classify if question is programming or theory based"""
    question_lower = question.lower()
    
    # Check for programming keywords
    for keyword in PROGRAMMING_KEYWORDS:
        if keyword in question_lower:
            return 'programming'
    
    # Check for theory keywords
    for keyword in THEORY_KEYWORDS:
        if keyword in question_lower:
            return 'theory'
    
    # Default to theory if unclear
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
    
    return 'python'  # Default to Python

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

Return ONLY the code with no explanations or markdown blocks."""
    else:
        prompt = f"""Generate an advanced, professional {language} code example for: {topic}

Requirements:
- Show best practices
- Include error handling if relevant
- Use proper design patterns
- Keep it under 10 lines but showcase expertise
- Add minimal but useful comments

Return ONLY the code with no explanations or markdown blocks."""
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            max_tokens=512,
        )
        
        code = chat_completion.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if code.startswith('```'):
            lines = code.split('\n')
            # Remove first line (```language) and last line (```)
            code = '\n'.join(lines[1:-1]) if len(lines) > 2 else code
            code = code.strip()
        
        return code if code else None
    except Exception as e:
        print(f"Error generating code: {str(e)}")
        return None

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
            model="llama-3.3-70b-versatile",  # Fast and smart model
            temperature=0.5,  # Lower temperature for more consistent formatting
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        mode = data.get('mode', 'beginner')  # Get mode from request
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        # STRICT: Check if question is technical/programming related
        if not is_technical_question(question):
            return jsonify(get_rejection_reason(question)), 400
        
        # Classify topic
        topic_type = classify_topic(question)
        language = detect_programming_language(question) if topic_type == 'programming' else None
        
        # Build AI prompt based on mode - ALWAYS 7 POINTS
        if mode == 'beginner':
            # Beginner mode - Simple explanation in EXACTLY 7 points
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
            # Advanced mode - Technical explanation in EXACTLY 7 points
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
        
        # Get AI response
        ai_result = call_ai_api(prompt)
        
        if not ai_result.get('success'):
            return jsonify({'error': 'AI service error'}), 500
        
        response_text = ai_result.get('response', '').strip()
        
        # Clean up response - remove any extra text before/after numbered list
        lines = response_text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Only keep lines that start with numbers
            if line and (line[0].isdigit() or (len(line) > 1 and line[0:2].replace('.', '').isdigit())):
                cleaned_lines.append(line)
        
        # Ensure we have exactly 7 points
        if len(cleaned_lines) < 7:
            # If less than 7, keep what we have
            response_text = '\n'.join(cleaned_lines)
        else:
            # If more than 7, take only first 7
            response_text = '\n'.join(cleaned_lines[:7])
        
        # Generate code example using AI if programming topic
        code_example = None
        if topic_type == 'programming' and language:
            code_example = get_code_example_from_ai(language, question, mode)
        
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

@app.route('/api/quiz', methods=['POST'])
def generate_quiz():
    try:
        data = request.get_json()
        topic = data.get('topic', 'Technical Interview').strip()
        
        # Generate 5 quiz questions
        quiz_prompt = f"""Generate exactly 5 technical interview questions about {topic}.
Format as numbered list only. No introductions or explanations.

1. [Question 1]
2. [Question 2]
3. [Question 3]
4. [Question 4]
5. [Question 5]"""
        
        ai_result = call_ai_api(quiz_prompt)
        
        if not ai_result.get('success'):
            return jsonify({'error': 'Quiz generation failed'}), 500
        
        return jsonify({
            'success': True,
            'questions': ai_result.get('response', '')
        })
        
    except Exception as e:
        print(f"Error in generate_quiz: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
    app.run(debug=True, port=5001)