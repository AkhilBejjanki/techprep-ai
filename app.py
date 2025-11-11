from flask import Flask, render_template, request, send_file
import google.generativeai as genai
import re
import os
import random
from dotenv import load_dotenv
from fpdf import FPDF

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# Sample technical topics
topics = [
    "Explain OOP concepts in Python",
    "What is normalization in SQL?",
    "Explain REST API and its methods",
    "What are Python decorators?",
    "Explain machine learning vs deep learning",
    "What is polymorphism in Java?",
    "What are joins in SQL?",
    "Explain Flask request and response cycle",
    "What is Docker and why is it used?",
    "What is version control in Git?"
]

# --- Text Cleaning Functions ---
def clean_markdown(text):
    """Remove markdown symbols like ** or ## from AI response"""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'\*', '', text)
    text = text.replace("##", "").replace("**", "")
    return text.strip()

def format_answer_to_list(answer_text):
    """Convert AI response into clean numbered points"""
    if not answer_text:
        return []

    text = re.sub(r'\r\n', '\n', answer_text)
    text = re.sub(r'\n{2,}', '\n\n', text).strip()

    lines = [ln.rstrip() for ln in text.split('\n')]

    items = []
    current = None
    new_item_re = re.compile(r'^\s*(?:\d+\s*[.)]|[-*•]|[–—])\s*(.*)')

    for ln in lines:
        ln_strip = ln.strip()
        if not ln_strip:
            if current:
                items.append(current.strip())
                current = None
            continue

        m = new_item_re.match(ln)
        if m:
            if current:
                items.append(current.strip())
            current = m.group(1).strip()
        else:
            if current is None:
                current = ln_strip
            else:
                current += ' ' + ln_strip

    if current:
        items.append(current.strip())

    clean_items = []
    for it in items:
        it = re.sub(r'\*\*(.*?)\*\*', r'\1', it)
        it = re.sub(r'[`~>#]+', '', it)
        it = it.strip()
        if it:
            clean_items.append(it)

    if not clean_items:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', answer_text) if p.strip()]
        if paragraphs:
            return paragraphs

    return clean_items

def is_technical(question):
    keywords = [
        "python", "java", "sql", "flask", "django", "machine", "learning",
        "oop", "data", "algorithm", "api", "react", "cloud", "developer", "ai", "docker", "git", "programming", "code", "software", "database", "network", "security", "linux", "javascript", "html", "css"
    ]
    return any(word in question.lower() for word in keywords)

# --- Main Route ---
@app.route("/", methods=["GET", "POST"])
def index():
    answer_items = None
    question = ""
    message = ""

    if request.method == "POST":
        if "suggest" in request.form:
            question = random.choice(topics)
        else:
            question = request.form.get("question", "")
            mode = request.form.get("mode")

            if not is_technical(question):
                message = "⚠️ Please ask a technical or programming-related question."
            else:
                prompt = f"""
                You are an AI technical interview assistant.
                Answer the following question in 5–8 concise numbered points.
                Each point should be short, direct, and clearly structured.
                Do not include markdown, emojis, or special formatting.
                If the user asks for 'simple mode', use beginner-friendly language.

                Mode: {mode}
                Question: {question}
                """

                try:
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    response = model.generate_content(prompt)
                    raw_answer = response.text.strip()
                    clean_text = clean_markdown(raw_answer)
                    answer_items = format_answer_to_list(clean_text)
                except Exception as e:
                    print("Error:", e)
                    message = "⚠️ AI model request limit reached. Please try again later."

    return render_template("index.html", answer_items=answer_items, question=question, message=message)


# --- PDF Download Route ---
@app.route("/download", methods=["POST"])
def download():
    answer_text = request.form.get("answer_text", "")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, answer_text)
    pdf.output("TechPrep_Answer.pdf")
    return send_file("TechPrep_Answer.pdf", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
