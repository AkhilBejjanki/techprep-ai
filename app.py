from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re

app = Flask(__name__)

#  Load API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

#  Function to clean markdown
def clean_markdown(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"##+", "", text)
    text = re.sub(r"[*_`#>-]", "", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()

#  Helper function to check if question is technical
def is_technical_question(question):
    technical_keywords = [
        "python", "java", "sql", "dbms", "machine learning", "ai", "html", "css", "react", "data",
        "algorithm", "dsa", "flask", "django", "oop", "object oriented", "cloud", "networking",
        "operating system", "linux", "c++", "coding", "programming", "array", "loop", "variable",
        "api", "function", "database", "pandas", "numpy", "tensorflow", "project", "developer"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in technical_keywords)

@app.route("/", methods=["GET", "POST"])
def home():
    question = ""
    answer = ""

    if request.method == "POST":
        question = request.form["question"].strip()

        # 🧠 Check if question is technical first
        if not is_technical_question(question):
            answer = "⚠️ Please ask only technical or programming-related questions."
            return render_template("index.html", question=question, answer=answer)

        try:
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            prompt = f"""
You are an AI interview assistant.
Answer only technical or programming-related questions in 5–8 short, point-wise statements.
If the question is non-technical, respond with "This question is out of technical scope."
Question: {question}
"""
            response = model.generate_content([prompt])
            raw_answer = response.text.strip() if hasattr(response, "text") else "No answer generated."
            answer = clean_markdown(raw_answer)

        except Exception as e:
            answer = f"Error: {str(e)}"

    return render_template("index.html", question=question, answer=answer)

if __name__ == "__main__":
    app.run(debug=True)
