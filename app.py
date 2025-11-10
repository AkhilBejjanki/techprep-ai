from flask import Flask, render_template, request
import google.generativeai as genai
import re

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key="AIzaSyCCpoIfIAzwQJKIYBUaIbOIGCYSNyzloV8")

# Function to clean markdown (##, **, etc.)
def clean_markdown(text):
    # Remove markdown headers and bold/italic markers
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # Remove **bold**
    text = re.sub(r"##+", "", text)                 # Remove headings ##
    text = re.sub(r"[*_`#>-]", "", text)            # Remove other markdown chars
    text = re.sub(r"\n\s*\n", "\n", text)           # Remove excessive blank lines
    return text.strip()

@app.route("/", methods=["GET", "POST"])
def home():
    question = ""
    answer = ""

    if request.method == "POST":
        question = request.form["question"].strip()

        try:

            model = genai.GenerativeModel("models/gemini-2.5-flash")


            prompt = f"""
You are an AI assistant that helps with technical interview preparation.
Answer the question briefly and clearly, in 5 to 8 concise bullet points.
Avoid long paragraphs or markdown formatting.

Question: {question}
"""

            response = model.generate_content([prompt])

            # Extract and clean up text
            raw_answer = response.text.strip() if hasattr(response, "text") else "No answer generated."
            answer = clean_markdown(raw_answer)

        except Exception as e:
            answer = f"Error: {str(e)}"

    return render_template("index.html", question=question, answer=answer)


if __name__ == "__main__":
    app.run(debug=True)
