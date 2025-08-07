import os
import re
import fitz  # PyMuPDF
# UPDATED imports to include render_template
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import shutil

# --- 1. CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("FATAL: GROQ_API_KEY environment variable not set. Please configure it.")
    exit()

# UPDATED: Initialize Flask to serve frontend files from templates/ and static/
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# --- Tesseract OCR Check ---
def is_tesseract_available():
    """Check if Tesseract is installed and in the system's PATH."""
    return shutil.which("tesseract") is not None

TESSERACT_AVAILABLE = is_tesseract_available()
if not TESSERACT_AVAILABLE:
    print("WARNING: Tesseract-OCR not found in system PATH. OCR functionality for scanned PDFs will be disabled.")

# --- 2. LLM AND PROMPT SETUP ---
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama3-70b-8192",
    temperature=0.2
)

mcq_prompt = PromptTemplate(
    input_variables=["context", "num_questions", "difficulty"],
    template="""You are a strict, instruction-following AI that generates perfectly formatted multiple-choice questions with explanations.

Based on the following text, generate exactly {num_questions} multiple-choice questions of {difficulty} difficulty.

---TEXT BEGINS---
{context}
---TEXT ENDS---

You MUST follow this format for EACH question. Do not deviate. Add a brief, one-sentence explanation for why the answer is correct.

**---START OF EXAMPLE---**
Question: What is the capital of France?
A) London
B) Berlin
C) Paris
D) Madrid
Correct Answer: C
Explanation: Paris is the official capital city of France, located in the north-central part of the country.
**---END OF EXAMPLE---**

Now, generate the questions.
"""
)

mcq_chain = mcq_prompt | llm | StrOutputParser()

# --- 3. HELPER FUNCTIONS ---

def perform_ocr_on_pdf(pdf_bytes):
    """
    Performs OCR on a PDF file's bytes to extract text.
    """
    if not TESSERACT_AVAILABLE:
        print("OCR skipped: Tesseract is not available.")
        return ""
        
    print("Performing OCR on the document...")
    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
        full_text = ""
        for i, image in enumerate(images):
            print(f"Processing page {i+1}/{len(images)} with OCR...")
            full_text += pytesseract.image_to_string(image) + "\n"
        print("OCR processing finished.")
        return full_text
    except Exception as e:
        print(f"An error occurred during OCR: {e}")
        return ""


def parse_mcq_text(mcq_text):
    """
    Parses the structured text output from the LLM into a list of question dictionaries.
    """
    questions = []
    pattern = re.compile(
        # This regex now broadly finds question blocks
        r"(?:Question|Q)\s*\d*\s*[:.]*\s*(?P<question>.+?)\s*"
        r"A\)\s*(?P<optA>.+?)\s*"
        r"B\)\s*(?P<optB>.+?)\s*"
        r"C\)\s*(?P<optC>.+?)\s*"
        r"D\)\s*(?P<optD>.+?)\s*"
        r"Correct Answer:\s*(?P<answer_letter>[A-D])\s*"
        r"Explanation:\s*(?P<explanation>.+?)(?=\n\s*(?:Question|Q)|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    cleaned_text = re.sub(r'\*\*', '', mcq_text)
    matches = pattern.finditer(cleaned_text)

    for match in matches:
        try:
            data = match.groupdict()
            
            # --- NEW, MORE ROBUST CLEANING LOGIC ---
            # Step 1: Get the raw captured question text
            raw_question = data['question'].strip()
            
            # Step 2: Define and remove the specific unwanted prefix
            garbage_prefix = "s based on the provided text:"
            if raw_question.lower().startswith(garbage_prefix):
                 raw_question = raw_question[len(garbage_prefix):].strip()

            # Step 3: The remaining text might still have a "Question X:" part. Remove it.
            # This ensures the final text starts with the actual question content.
            final_question = re.sub(r'^(?:Question|Q)\s*\d*\s*[:.]*\s*', '', raw_question, flags=re.IGNORECASE).strip()
            # --- END NEW CLEANING LOGIC ---

            options = [
                data['optA'].strip(),
                data['optB'].strip(),
                data['optC'].strip(),
                data['optD'].strip()
            ]
            
            answer_letter = data['answer_letter'].strip().upper()
            answer_index = ord(answer_letter) - ord('A')
            answer_text = options[answer_index]

            questions.append({
                "question": final_question, # Use the fully cleaned question
                "options": options,
                "answer": answer_text,
                "explanation": data['explanation'].strip()
            })
        except (KeyError, IndexError) as e:
            print(f"Skipping a malformed block identified by regex. Error: {e}")
            continue
            
    print(f"Successfully parsed {len(questions)} questions with explanations.")
    return questions

# --- 4. API ENDPOINTS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Frontend endpoint to check for OCR capability."""
    return jsonify({
        "ocr_available": TESSERACT_AVAILABLE,
        "tesseract_version": pytesseract.get_tesseract_version().strip() if TESSERACT_AVAILABLE else None,
        "error": "Tesseract-OCR executable not found in PATH." if not TESSERACT_AVAILABLE else None
    })

@app.route('/generate-quiz', methods=['POST'])
def generate_quiz():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            pdf_bytes = file.read()
            text = ""

            print("Attempting direct text extraction with PyMuPDF...")
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                text = "".join(page.get_text() for page in doc)

            if len(text.strip()) < 100 and TESSERACT_AVAILABLE:
                print("Direct extraction yielded little text. Falling back to OCR.")
                text = perform_ocr_on_pdf(pdf_bytes)
            elif len(text.strip()) < 100 and not TESSERACT_AVAILABLE:
                 print("Direct extraction failed, and OCR is not available. Cannot process file.")
                 return jsonify({"error": "Could not extract text from this PDF, and the OCR engine is not available. The file might be an image-only PDF."}), 400

            if not text.strip():
                return jsonify({"error": "Could not extract text from the PDF, even after attempting OCR."}), 400

            num_questions = int(request.form.get('num_questions', 5))
            difficulty = request.form.get('difficulty', 'Medium')
            
            print(f"Generating {num_questions} {difficulty} questions from extracted text...")
            shortened_text = text[:12000]

            llm_output = mcq_chain.invoke({
                "context": shortened_text,
                "num_questions": num_questions,
                "difficulty": difficulty
            })
            
            questions = parse_mcq_text(llm_output)
            
            if not questions:
                print("----------- RAW AI OUTPUT (PARSING FAILED) -----------")
                print(llm_output)
                print("-----------------------------------------------------")
                return jsonify({"error": "The AI model failed to generate questions in the correct format."}), 500

            return jsonify({"questions": questions})

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    return jsonify({"error": "Invalid file type"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)