from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re

app = Flask(__name__)

# Load environment variables from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Configure Gemini with your API key
genai.configure(api_key=api_key)

# Function to clean markdown (remove ##, **, etc.)
def clean_markdown(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # Remove **bold**
    text = re.sub(r"##+", "", text)                 # Remove headings ##
    text = re.sub(r"[*_`#>-]", "", text)            # Remove other markdown chars
    text = re.sub(r"\n\s*\n", "\n", text)           # Remove extra blank lines
    return text.strip()

@app.route("/", methods=["GET", "POST"])
def home():
    question = ""
    answer = ""

    if request.method == "POST":
        question = request.form["question"].strip()

        try:
            #  Use the latest Gemini model
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            #  Prompt for concise, point-wise answers
            prompt = f"""
You are an AI assistant that helps with technical interview preparation.
Answer this question in a clear, short, point-wise format (maximum 6 points).
Avoid long paragraphs or markdown formatting.

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
