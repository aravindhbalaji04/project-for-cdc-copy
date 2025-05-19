import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import os
import json
from ats_score import calculate_score  # Ensure this function accepts parsed JSON text
from external_parameters import analyze_resume
import re
import tempfile

# 🧠 Configure Google Gemini API
os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# 📝 Gemini Prompt Template
PROMPT_TEMPLATE = """
You are a deterministic and highly consistent resume parser and evaluator. Your job is to extract resume content in a structured JSON format and evaluate it with strict, repeatable rules — always producing the same result for the same input.

---

### Step 1: Structured Resume Data Extraction

Extract and organize the candidate’s information into the following *exact JSON format*:

{
  "Contact Information": {
    "name": "...",
    "email": "...",
    "phone": "...",
    "linkedin": "...",  // null if missing
    "location": "..."   // null if missing
  },
  "Summary": "...", // 1-3 sentence summary, null if missing
  "Education": [
    {
      "institution": "...",
      "degree": "...",
      "department": "...",
      "cgpa": "...", // null if missing
      "year_of_completion": "..." // year only, null if missing
    }
  ],
  "Skills": {
    "Languages": [...],
    "Technologies": [...],
    "Core": [...]
  },
  "Certifications": ["..."],  // Empty array if none
  "Projects": [
    {
      "title": "...",
      "date": "...", // null if missing
      "details": ["..."]
    }
  ],
  "Work Experience": [
    {
      "role": "...",
      "organization": "...",
      "location": "...", // null if missing
      "date": "...",
      "responsibilities": ["..."]
    }
  ]
}

---

### Step 2: Resume Evaluation - Atomic-Level Scoring (100 Points Total)
1. SECTION HEADINGS (15 pts)
   15 = All 6 standard sections with exact headers
   12 = 1 non-standard header (e.g., "My Journey")
   9 = 2 non-standard headers
   6 = Missing 1 required section
   3 = Missing 2 required sections
   0 = Missing ≥3 sections

2. ATS PARSE RATE (25 pts)
   25 = Perfect single-column, no tables/graphics
   20 = Minor spacing issues (1-2 instances)
   15 = Non-standard fonts OR 1-2 images
   10 = Single-column tables present
   5 = Multi-column layout detected
   0 = Complex graphics/tables making text unparsable

3. ACTION VERB REPETITION (10 pts)
10 = No action verbs repeated >1 time
8 = 1-2 action verbs repeated twice 
6 = 3-4 action verbs repeated twice
4 = 5-6 action verbs repeated twice OR 1 verb repeated 3+ times
2 = 7-8 action verbs repeated twice OR 2 verbs repeated 3+ times
0 = 9+ repeated action verbs OR 3+ verbs repeated 3+ times

Action Verbs List (Partial):
["managed", "led", "developed", "created", "implemented", 
"designed", "improved", "increased", "reduced", "optimized",
"coordinated", "facilitated", "performed", "achieved", "built"]

Rules:
1. Count ONLY verbs from predefined action verb list
2. Different tenses count as same verb (manage/managed/managing)
3. Must appear in bullet points (ignore summary/headers)
4. Consecutive bullets count as separate instances

4. GRAMMAR/LANGUAGE (15 pts)
   15 = Flawless grammar and consistent tense
   12 = 1-2 minor errors
   9 = 3-4 errors OR 1 tense inconsistency
   6 = 5 errors OR 2 tense inconsistencies
   3 = 6+ errors with poor phrasing
   0 = Unreadable due to language issues

5. BUZZWORD USE (20 pts)
   20 = All buzzwords supported by quantifiable results
   15 = 1 unsupported buzzword
   10 = 2 unsupported buzzwords
   5 = 3 unsupported buzzwords
   0 = 4+ unsupported buzzwords

6. ACTIVE VOICE (15 pts)
   15 = 90%+ active voice
   12 = 80-89% active voice
   9 = 70-79% active voice
   6 = 60-69% active voice
   3 = 50-59% active voice
   0 = <50% active voice

### SCORING RULES:
1. Always round DOWN to nearest integer
2. Identical errors → identical deductions
3. Count ALL instances (no subjective exceptions)
4. Re-verify ambiguous cases against original text
### Step 3: Output Format

Return only this JSON structure — no extra comments, headings, or notes:

{
  "Extracted Data": { ... },
  "Miscellaneous Score": {
    "Section Headings": { "score": ..., "feedback": "..." },
    "ATS Parse Rate": { "score": ..., "feedback": "..." },
    "Repetition": { "score": ..., "feedback": "..." },
    "Grammar and Language": { "score": ..., "feedback": "..." },
    "Buzzwords": { "score": ..., "feedback": "..." },
    "Active Voice": { "score": ..., "feedback": "..." },
  }
  "Miscellaneous Score" : "Section Headings + ATS Parse Rate + Repetition + Grammar Language + Buzzwords + Active Voice"
}

---

### Final Consistency Rules (Non-Negotiable):

- No subjective judgment: Only match phrases, words, and formats against predefined lists or patterns.
- Passive voice is detected only if it matches strict regex: (was|were|been|being) \w+ed
- Buzzwords only count if directly followed by a number or measurable outcome (e.g., "reduced by 10%", "delivered 3 projects").
- Repetition is case-insensitive exact match. "Developed" ≠ "develops".
- Grammar deductions only come from a fixed error list. Do not deduct for tone, wordiness, or preferences.
- Do not infer — extract what is literally present in the text.
- Use a static list of penalized buzzwords: ["team player", "go-getter", "self-starter", "passionate"]
- All score deductions are binary — either applied or not, no partial scores.
- Reuse the same tokenizer and regex engine for every parse to prevent platform-level tokenization drift.
- Output must be *bit-for-bit identical* for identical input strings.

---

Now, analyze the resume below:

{resume_text}
"""

# 📤 Extract text from PDF using PyMuPDF
def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    resume_text = "\n".join(page.get_text() for page in doc)
    return resume_text

# 🤖 Ask Gemini to parse the resume
def parse_resume_with_gemini(resume_text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = PROMPT_TEMPLATE.replace("{resume_text}", resume_text)
    response = model.generate_content(prompt)
    # Clean any code block backticks (```json or ```)
    clean_text = re.sub(r"^```(?:json)?|```$", "", response.text.strip(), flags=re.MULTILINE).strip()
    return clean_text


# 🚀 Streamlit App
st.title("📄 ATS SCORE")
st.markdown("Upload a resume PDF")

uploaded_file = st.file_uploader("Drag and drop a resume PDF here", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("🔍 Extracting text from PDF..."):
        resume_bytes = uploaded_file.read()
        resume_text = extract_text_from_pdf(uploaded_file)

    with st.spinner("🤖 Parsing resume with Gemini..."):
        parsed_json_text = parse_resume_with_gemini(resume_text)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
      temp_file.write(resume_bytes)
      temp_path = temp_file.name

    try:
        parsed_output = json.loads(parsed_json_text)
        st.success("✅ Resume successfully parsed!")
        st.subheader("🧾 Parsed Resume (JSON):")
        st.json(parsed_output)

        st.subheader("📊 ATS Score:")
        ats_score = calculate_score(parsed_output, analyze_resume(temp_path))
        st.write(f"**Score:** {ats_score}/100")

    except Exception as e:
        st.error("⚠️ Failed to parse JSON output.")
        st.text(f"Raw Output:\n{parsed_json_text}")
        st.text(f"Error: {e}")


# if __name__ == "__main__":
#     st.set_page_config(page_title="ATS Resume Evaluator")
#     st.title("📄 AI Resume Evaluator")
#     uploaded_file = st.file_uploader("Upload your resume (PDF only)", type="pdf")

#     if uploaded_file:
#         with tempfile.NamedTemporaryFile(delete=False) as tmp:
#             tmp.write(uploaded_file.read())
#             tmp_path = tmp.name

#         with fitz.open(tmp_path) as doc:
#             text = ""
#             for page in doc:
#                 text += page.get_text()

#         # Call Gemini parser
#         model = genai.GenerativeModel('gemini-1.5-flash')
#         parsed = model.generate_content(PROMPT_TEMPLATE + text).text

#         # Parse & score
#         format_score = analyze_resume(text)
#         final_score = calculate_score(parsed, format_score)

#         st.subheader("🎯 ATS Score")
#         st.write(f"**Final Score**: {final_score}/100")
#         st.json(parsed)
