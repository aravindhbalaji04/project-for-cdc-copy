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

<<<<<<< HEAD
=======
# Work Experience Analysis Prompt
WORK_EXPERIENCE_PROMPT = """
You are an AI-powered resume evaluation engine for an advanced ATS system. Your task is to analyze the candidate's work experience and internships, scoring them out of 100 based on multiple factors. The goal is to provide a more accurate score compared to current ATS systems, by considering both traditional factors and new-age performance metrics, skills, and broader contexts.

### 1. Experience Relevance to Job Description (JD) and Industry Trends:
   - Direct Role Match: If the experience is directly related to the JD in terms of role title, responsibilities, and tools used, assign higher scores (80-100).
     - Example: If the JD specifies Software Engineer with experience in Java, and the candidate worked as a Java Software Engineer, give a high score (85-100).
   - Indirect Role Match: If the candidate has experience in similar roles or skills that relate to the JD but not a direct title match, assign moderate scores (60-80).
     - Example: If the JD requires Cloud Architect, and the candidate has worked as a Cloud Engineer, give a moderate score (70-80).
   - Industry Trends Relevance: Experience should reflect current industry trends or cutting-edge technologies (e.g., AI, IoT, Blockchain). Experience that involves trending technologies should be scored higher (70-90).
     - Example: Experience with AI in Production Systems should score higher for alignment with modern trends.
   - No Match: If the experience is irrelevant to the JD, assign low or no score.
     - Example: Experience in customer support for a Software Engineer position should score low (10-30).
   - Emerging Sector Relevance: Experience related to newer, disruptive technologies like Quantum Computing, Autonomous Systems, or Edge Computing should receive bonus points (10-20).
     - Example: A candidate with experience in Quantum Computing should score higher for forward-thinking skills.

### 2. Internship Relevance & Impact:
   - Remote Internships: Assign a lower score (10-15% reduction) for virtual internships due to reduced interaction.
   - Offline Internships: Assign a higher score (5-10% increase) for in-person internships due to richer learning experiences and hands-on involvement.
   - Internship Duration: Longer internships should receive higher scores (6+ months: 70-80), while shorter internships (3 months or less) receive moderate to low scores (40-60).
   - Impact of Internship: If the internship resulted in a concrete product, feature, or business contribution, assign additional bonus points (10-20).
     - Example: An internship leading to a successful product launch or team leadership role will score higher.
   - Internship Innovation: Assign extra points if the internship resulted in innovative contributions like creating a new tool, solving a critical business problem, or presenting unique insights (15-20).

### 3. Years of Work Experience & Professional Growth:
   - Early Career (1-3 years): Scores based on technical skill development and hands-on experience. A good score (60-75) if they show strong technical expertise in core areas.
   - Mid-Career (4-6 years): Experience should demonstrate increased responsibility, project management, or team leadership (70-85).
   - Senior Career (7+ years): Experience should reflect high-level strategic impact, team leadership, and mentoring roles (80-100).
   - High-impact Projects: Assign bonus points for leadership roles in high-profile projects that generated substantial revenue or optimized business processes (15-30).

### 4. Skill Alignment:
   - Skills Match: Direct match between JD and the candidate's skills (technical & soft) should score higher (70-90).
   - Advanced Skills: Bonus points for advanced skills, such as AI/ML, Cloud Architecture, and Cybersecurity certifications.
   - Emerging Technologies: Assign extra points for experience with emerging technologies that are pivotal for future-proofing the role.
   - Skills Beyond JD: If the candidate possesses additional relevant skills, award bonus points (10-20).
   - Multi-domain Expertise: Extra points for cross-disciplinary expertise (10-15).

### 5. Impactful Contributions:
   - Problem-Solving: Identify specific problems the candidate has solved. Assign additional points for measurable impacts.
   - Leadership and Innovation: Evaluate whether the candidate has contributed to innovative solutions, led teams, or been a key decision-maker in projects.
   - Recognition: Award extra points for professional awards, recognitions, or patents.
   - Customer or Client Impact: Extra points for candidates who have delivered projects that led to client satisfaction, customer retention, or business growth.

### 6. Soft Skills & Cultural Fit:
   - Communication: Assign higher scores to candidates whose roles involved cross-functional communication.
   - Team Collaboration: Evaluate whether the candidate worked in Agile teams or was a collaborative team player.
   - Mentorship: Assign higher scores to candidates who have been involved in training, mentoring, or building teams.

### 7. Additional Factors:
   - Geographic Relevance: Consider the JD's requirement for location-based skills.
   - Diversity of Experience: Evaluate whether the candidate has a diverse work history.
   - Work Environment: If the JD emphasizes familiarity with specific work environments, prioritize candidates who have worked in those settings.
   - Workplace Adaptability: Evaluate how well the candidate has adapted to changing workplace environments.
   - Volunteer Experience: Award points for volunteer or pro-bono work.
   - Passion Projects: Award points for side projects or open-source contributions.

### Required Output Format:
{
  "scores": {
    "Experience_Relevance": {
      "score": X,
      "breakdown": {
        "direct_match": X,
        "indirect_match": X,
        "industry_trends": X,
        "emerging_tech": X
      }
    },
    "Internship_Impact": {
      "score": X,
      "breakdown": {
        "duration": X,
        "impact": X,
        "innovation": X
      }
    },
    "Professional_Growth": {
      "score": X,
      "breakdown": {
        "years_experience": X,
        "responsibility_level": X,
        "high_impact_projects": X
      }
    },
    "Skill_Alignment": {
      "score": X,
      "breakdown": {
        "required_skills": X,
        "advanced_skills": X,
        "emerging_tech": X,
        "additional_skills": X
      }
    },
    "Impactful_Contributions": {
      "score": X,
      "breakdown": {
        "problem_solving": X,
        "leadership": X,
        "recognition": X,
        "client_impact": X
      }
    },
    "Soft_Skills": {
      "score": X,
      "breakdown": {
        "communication": X,
        "teamwork": X,
        "mentorship": X
      }
    },
    "Additional_Factors": {
      "score": X,
      "breakdown": {
        "geographic": X,
        "diversity": X,
        "workplace": X,
        "volunteer": X,
        "passion_projects": X
      }
    },
    "raw_total": X,
    "final_score": X
  },
  "detailed_analysis": {
    "strengths": ["..."],
    "areas_for_improvement": ["..."],
    "recommendations": ["..."]
  }
}

Now analyze the following work experience:
{work_experience}
"""

# Achievements Analysis Prompt
ACHIEVEMENTS_PROMPT = """
You are an expert AI resume evaluator assigned to *only analyze the Achievements section* of a candidate's resume. Your task is to assess the strength, credibility, and relevance of each achievement and give a *highly accurate, explainable score out of 100*.

Use the comprehensive scoring framework below to evaluate each point thoroughly. Your response should reflect deep understanding of *technical depth, **industry impact, and **role relevance*. 

Your evaluation should reflect the perspective of a *senior recruiter, tech lead, or domain expert*, considering what genuinely adds hiring value and what's generic or inflated.

---

### 🔍 Key Evaluation Dimensions (Total: 100 Points)

1. ✅ *Relevance to Job Role (25 Points)*
- Evaluate how closely the achievement aligns with the role's required skills, technologies, or goals.
- Give full points to achievements that demonstrate *direct application* of key job requirements.
- Distinguish between general and specialized relevance.
- Bonus: If candidate tailored this for the current job role → +2

2. 📊 *Impact & Quantified Results (20 Points)*
- Was the achievement measurable?
- Prioritize those that quantify success (%, $, # users, hours saved, etc.).
- Scale of impact matters: enterprise vs. college vs. personal.
- Bonus: Global-scale, high-user impact (+2)

3. 🧠 *Ownership & Initiative (15 Points)*
- Did the candidate lead or initiate the project?
- Distinguish between:
  - Passive participation (low score)
  - Active contribution
  - Full ownership or leadership (high score)
- Prefer "initiated," "proposed," "built," "led," etc., over "helped," "contributed to"

4. 🔬 *Technical Difficulty & Innovation (15 Points)*
- Rate the complexity and challenge level.
- Use of AI, ML, LLMs, distributed systems, cloud-native stacks, or security = higher points.
- Projects with high abstraction, architectural design, or cross-domain integration score higher.
- Bonus: Published model, deployed system at scale, performance-optimized

5. 🏆 *Recognition & Awards (10 Points)*
- Value certifications, awards, recognitions, publications, patents.
- Specially score *hackathons and coding competitions* based on level:
  - 🥇 International Winner: +10
  - 🥈 National Runner-up: +8
  - College/Local events: +2 to +5
- Bonus: If award is prestigious (e.g., Smart India Hackathon, Kaggle Grandmaster, ICPC Regionals)

6. 🗣 *Soft Skills Demonstrated (5 Points)*
- Does the candidate show teamwork, leadership, public speaking, organizing skills, etc.?
- e.g., "Led club of 50+ students", "Mentored juniors", "Speaker at event"
- Penalize if all achievements are purely individual or silent on collaboration

7. ⏳ *Consistency Over Time (5 Points)*
- Evaluate if achievements are sustained across years or jammed into a short period.
- Prefer those who consistently participated/won over time.
- Bonus: If there's evidence of year-on-year growth or role elevation

8. 💡 *Initiative / Problem-Solving Ability (5 Points)*
- Score higher if the achievement was self-initiated, creative, or solved a real-world problem.
- Prefer "identified gap and fixed it" over "implemented something given"

9. 🧩 *Domain/Industry-Specific Value (5 Points)*
- Some accomplishments are more valuable depending on domain:
  - GitHub repo with 100+ stars for Dev roles
  - Research papers with citations for academia
  - Revenue/campaign growth for business/marketing
- Score based on contextual fit to the job domain

10. 🔀 *Cross-Disciplinary or Scalable Impact (5 Points)*
- Does the achievement span multiple disciplines or domains?
- Did it scale to larger audiences (e.g., thousands of users, national usage)?
- Prefer solutions used by others (e.g., SaaS, APIs, open source adoption)

### Required Output Format:
{
  "scores": {
    "Relevance_to_Job_Role": {
      "score": X,
      "breakdown": {
        "direct_application": X,
        "specialized_relevance": X,
        "tailoring_bonus": X
      }
    },
    "Impact_and_Quantified_Results": {
      "score": X,
      "breakdown": {
        "measurability": X,
        "scale_of_impact": X,
        "global_impact_bonus": X
      }
    },
    "Ownership_and_Initiative": {
      "score": X,
      "breakdown": {
        "leadership_level": X,
        "initiative_demonstrated": X
      }
    },
    "Technical_Difficulty": {
      "score": X,
      "breakdown": {
        "complexity": X,
        "innovation": X,
        "technical_bonus": X
      }
    },
    "Recognition_and_Awards": {
      "score": X,
      "breakdown": {
        "awards": X,
        "competitions": X,
        "prestige_bonus": X
      }
    },
    "Soft_Skills": {
      "score": X,
      "breakdown": {
        "teamwork": X,
        "leadership": X,
        "communication": X
      }
    },
    "Consistency": {
      "score": X,
      "breakdown": {
        "time_span": X,
        "growth_evidence": X
      }
    },
    "Problem_Solving": {
      "score": X,
      "breakdown": {
        "initiative": X,
        "creativity": X
      }
    },
    "Domain_Value": {
      "score": X,
      "breakdown": {
        "industry_relevance": X,
        "domain_specific": X
      }
    },
    "Cross_Disciplinary": {
      "score": X,
      "breakdown": {
        "multi_domain": X,
        "scalability": X
      }
    },
    "raw_total": X,
    "final_score": X
  },
  "detailed_analysis": {
    "standout_achievements": ["..."],
    "red_flags": ["..."],
    "job_match_analysis": ["..."],
    "technical_evidence": ["..."]
  }
}

Now analyze the following achievements:
{achievements_section}
"""

# Certification Analysis Prompt
CERTIFICATION_PROMPT = """
You are a highly skilled AI Resume Evaluator, assigned to thoroughly analyze the Certifications section of a candidate's resume. Your objective is to assess each certification for *job role relevance, credibility, recency, depth, and hiring value, and provide a **well-justified, consistent score out of 100*, using an expanded, rigorous framework.

You must think like a *senior technical recruiter, hiring manager, or domain expert* who understands hiring value—not just content—but how certifications influence actual decisions. Your response should reflect *deep analytical reasoning, **fact-based issuer judgment, and **score consistency* across diverse roles and backgrounds.

---

## 🧾 Target Job Role Context:
{job_description}

---

## 📜 Candidate's Certifications:
{certifications_section}

---

## ✅ Evaluation Dimensions (Total: 100 Points)

### 1. 🎯 Relevance to Job Role & Skill Stack (30 Points)
- Is the certification directly tied to job-required skills, tools, frameworks, cloud, platforms, or techniques?
- 27–30: Direct match to stack or function (e.g., AWS DevOps cert for AWS DevOps job)
- 20–26: Partial but technical alignment (e.g., Python cert for AI Engineer role)
- 10–19: Somewhat relevant but too foundational/generic
- 0–9: Off-topic (e.g., Excel cert for Backend Developer)
- Check for keyword and technology overlap (frameworks, clouds, stacks, security, infra)
- Bonus (+2): If the certification clearly looks selected to match the current role or signals domain preparation.

---

### 2. 🏅 Issuer Authority & Legitimacy (20 Points)
- Score based on issuer tier, industry respect, global validity, and verification ability.
#### Issuer Tiers:
| Tier | Examples | Range |
|------|----------|-------|
| 🥇 Tier 1 (Global Tech/Edu Giants) | Google Cloud, AWS, Microsoft, Stanford, MIT, ISC², Oracle, PMI | 18–20 |
| 🥈 Tier 2 (Top EdTech/Platforms) | Coursera + Top Univ, edX, Udacity, LinkedIn Learning + company badges | 14–17 |
| 🥉 Tier 3 (Mid-range/Emerging) | Udemy (varies by instructor), Coding Ninjas, GreatLearning | 8–13 |
| 🚫 Tier 4 (Unknown/Unverifiable) | Random sites, PDF-only certs, "Academy of AI Excellence" | 0–7 |
- *Validate issuer domain name, public presence, and badge authenticity*
- Bonus (+2): If cert has a public credential URL or comes from a verifiable issuing body.

---

### 3. 📅 Recency, Validity & Tech Freshness (10 Points)
- 10: Issued in the past 6–12 months, active, non-expired, up-to-date stack
- 8–9: Issued 1–2 years ago, still relevant
- 5–7: Older but in a slow-moving domain (e.g., SQL, PMP)
- 3–4: Tech changes fast, cert outdated (e.g., Hadoop in 2024)
- 0–2: Expired or deprecated tools (e.g., Flash, AngularJS)
- Bonus (+2): If the cert has a clear expiration/renewal system and candidate has renewed.

---

### 4. 🎓 Technical Depth, Exam Rigor & Content Format (15 Points)
- 13–15: Includes multi-stage exam, timed project, or lab (e.g., AWS Pro, GCP Architect)
- 10–12: Contains hands-on assignments or graded capstone
- 6–9: Recorded videos + MCQ + basic quizzes
- 3–5: Passive content, easy to complete in <2 days
- 0–2: "Click-to-certify" programs with no validation
- Bonus (+2): Includes public GitHub repos, project links, or real-world simulation demos

---

### 5. 🔬 Specialization, Differentiation & Topic Uniqueness (10 Points)
- 9–10: Niche topic directly applicable (e.g., LLMOps, Kubernetes Security, SRE Observability)
- 6–8: Mid-level specialization (e.g., Cloud Fundamentals, Web Dev Bootcamp)
- 3–5: Basic, redundant, or multiple certs on same topic
- 0–2: No unique learning, repeating same concept (e.g., 3 Python intro certs)
- Penalize lack of topic diversity if multiple certs address the same tool at basic level

---

### 6. 🔧 Stack, Tool, Framework, or Platform Match (5 Points)
- 5: Certifications focus on tools, frameworks, clouds used in the JD
- 3–4: Indirect connection (e.g., "Data Cleaning with Python" for a Cloud Data Engineer)
- 1–2: Vague or too generic ("Full Stack Basics")
- 0: No overlap with required tools/tech

---

### 7. 🛡 Industry Recognition & Hiring Influence (5 Points)
- 5: Certification is well-regarded in hiring pipelines or mandatory in industry (e.g., CISSP, PMP, AWS Pro)
- 3–4: Optional but respected (e.g., AZ-104, Google Data Analytics)
- 1–2: Seen as effort signal, not a hiring filter
- 0: No impact on real-world hiring (PDF-only badges, unknown issuer)

---

### 8. 📈 Growth Path, Continuity & Level Progression (5 Points)
- 5: Certifications show level growth (e.g., AWS Practitioner → Associate → Pro)
- 3–4: Some upward movement (Beginner → Intermediate)
- 1–2: Random certs with no clear structure
- 0: Only one certification or all done at same level/time

---

### 9. 📂 Evidence of Project Work / Hands-On Application (5 Points)
- 5: Links to GitHub, notebooks, published APIs, ML models, public dashboards
- 3–4: Mentions projects but no proof
- 1–2: No project-based work stated
- 0: Purely theoretical certifications with no deliverables
- Bonus (+2): Evidence of model deployment, SaaS tool, or proof of real-world use

---

### 10. 🔁 Redundancy, Bloat, or Certification Clutter (Negative Scoring)
- -5: Multiple certs covering same exact skill (e.g., 3 Python beginner courses)
- -3: Irrelevant or filler certs (e.g., "Leadership in Social Work" for Data Engineer)
- -2: Buzzwordy cert names (e.g., "AI Mastery" with no proof or syllabus)
- -1: Obsolete or deprecated tech covered
- Note: Apply these as negative adjustments after scoring

---

## ➕ Supplementary Checks
- ✅ Public credential links = +1–2 per cert
- ✅ Certs with company endorsement or used internally = +2
- ✅ Projects graded by instructors or proctored exams = +1–3
- ✅ Certs shared with hiring feedback = +2

---

## 📤 Output Format

Return the result in the following structure:

{
  "scores": {
    "Relevance_to_Job": {
      "score": X,
      "breakdown": {
        "direct_match": X,
        "technical_alignment": X,
        "bonus": X
      }
    },
    "Issuer_Credibility": {
      "score": X,
      "breakdown": {
        "issuer_tier": X,
        "verification": X,
        "bonus": X
      }
    },
    "Recency": {
      "score": X,
      "breakdown": {
        "validity": X,
        "tech_freshness": X,
        "bonus": X
      }
    },
    "Technical_Rigor": {
      "score": X,
      "breakdown": {
        "exam_format": X,
        "hands_on": X,
        "bonus": X
      }
    },
    "Specialization": {
      "score": X,
      "breakdown": {
        "topic_uniqueness": X,
        "diversity": X
      }
    },
    "Stack_Match": {
      "score": X,
      "breakdown": {
        "tool_overlap": X,
        "framework_match": X
      }
    },
    "Hiring_Value": {
      "score": X,
      "breakdown": {
        "industry_recognition": X,
        "hiring_influence": X
      }
    },
    "Progression": {
      "score": X,
      "breakdown": {
        "level_growth": X,
        "continuity": X
      }
    },
    "Project_Evidence": {
      "score": X,
      "breakdown": {
        "hands_on_proof": X,
        "real_world_use": X,
        "bonus": X
      }
    },
    "Deductions": {
      "score": X,
      "breakdown": {
        "redundancy": X,
        "irrelevance": X,
        "obsolete": X
      }
    },
    "raw_total": X,
    "final_score": X
  },
  "detailed_analysis": {
    "best_certifications": ["..."],
    "weak_certifications": ["..."],
    "domain_match": ["..."],
    "improvement_suggestions": ["..."],
    "redundancy_issues": ["..."]
  }
}

Now analyze the following certifications:
{certifications_section}
"""

>>>>>>> 65ceaf0bbb7a9876eb84a9123521d3c0b31d8a3a
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
<<<<<<< HEAD


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
=======
>>>>>>> 65ceaf0bbb7a9876eb84a9123521d3c0b31d8a3a
