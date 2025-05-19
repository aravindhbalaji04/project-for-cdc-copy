import google.generativeai as genai
import re
import json

genai.configure(api_key="AIzaSyDfzvb_QnYsh0S_0Yk4LWVcvTiU936zjuo")

model = genai.GenerativeModel('gemini-1.5-flash')

def calculate_score(parsed_output, format_score):
    prompt = """
    You are an AI-powered resume evaluation engine for an advanced ATS system. Your task is to analyze the candidate's work experience and internships, scoring them out of 100 based on strictly defined criteria. 

    ### Evaluation Rules:
    1. Scoring must be consistent for identical inputs
    2. Each category has predefined scoring ranges
    3. Bonus points must be applied exactly as specified
    4. Penalties must be applied exactly as specified
    5. Final score is calculated as: (Sum of category scores)/4

    ### Strict Scoring Rubric:

    1. Experience Relevance (Max 50)
    - 45-50: Exact role match + required tools + industry trends
    - 40-44: Near-exact role match + most tools
    - 35-39: Related role + some tools
    - 30-34: Somewhat related role
    - 0-29: Unrelated experience
    - Penalty: -10 for each missing required tool/technology

    2. Internship Quality (Max 50)
    - 45-50: 6+ months in-person + measurable impact + innovation
    - 40-44: 6+ months in-person + measurable impact
    - 35-39: 3-6 months in-person
    - 30-34: 3-6 months remote
    - 25-29: <3 months in-person
    - 20-24: <3 months remote
    - Bonus: +10 for published work/product launch (Don't Add if Score is already 41 or greater)
    - Penalty: -15 for virtual-only internships

    3. Skill Alignment (Max 100)
    - 90-100: All required skills + advanced certifications
    - 80-89: All required skills + some certifications
    - 70-79: Most required skills
    - 60-69: Some required skills
    - 0-59: Few required skills
    - Bonus: +5 per relevant certification beyond requirements

    4. Impactful Contributions (Max 100)
    - Quantifiable impacts only (must include metrics)
    - 20 points per major impact (max 100)
    - Must include: what changed + by how much + timeframe

    5. Soft Skills (Max 100)
    - 25 points per category (communication, teamwork, leadership, mentoring)
    - Must have specific examples for each point awarded

    6. Miscellaneous Score from Resume Evaluation, ATS Parse Rate, Repetition,
      Grammar & Language, Buzzwords, Active Voice (Max 100)

    7. Format Score at the end of this prompt (Max 100)

    ### Strict Evaluation Process:
    1. Analyze each section separately
    2. Apply scores exactly as defined in rubric
    3. Calculate weighted final score using:
    - 45% weight for Skill Alignment score
    - 15% weight for Experience Relevance score
    - 15% weight for Internship Quality score
    - 5% weight for Soft Skills score
    - 10% weight for Impactful Contributions score
    - 5% weight for Miscellaneous Score
    - 5% weight for Format Score
    4. Compute final score using formula:
    Final Score = (0.45 × Skill_Alignment) + 
                    (0.15 × Experience_Relevance) + 
                    (0.15 × Internship_Quality) + 
                    (0.05 × Soft_Skills) + 
                    (0.10 × Impactful_Contributions) +
                    (0.05 x Miscellaneous_Score) +
                    (0.05 x Format_Score)
    5. Round to nearest whole number
    6. Never deviate from predefined weights or ranges
    7. Ensure sum of all weights equals exactly 1.0 (100%)

    ### Required Output Format:
    {
    "scores": {
        "Skill_Alignment": X,        # 45% weight
        "Experience_Relevance": X,   # 15% weight
        "Internship_Quality": X,     # 15% weight
        "Soft_Skills": X,           # 5% weight
        "Impactful_Contributions": X, # 10% weight
        "Miscellaneous_Score": X, # 5% weight
        "Format_Score": X, # 5% weight
        "weighted_total": X         # Calculated final score
    },
    "evaluation": "Brief justification of scores"
    }
    """ + f"{parsed_output} and " + f"Format_score = {format_score}"

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.0, top_p=1.0, top_k=1)
    )

    # Clean backtick formatting if present
    raw_text = re.sub(r"^```(?:json)?|```$", "", response.text.strip(), flags=re.MULTILINE).strip()

    # Extract only JSON part from Gemini's output
    json_match = re.search(r"\{.*?\"weighted_total\"\s*:\s*\d+\s*\}.*?\}", raw_text, re.DOTALL)

    if json_match:
        json_string = json_match.group(0)
        try:
            data = json.loads(json_string)
            print(data)
            print()
            return data["scores"]["weighted_total"]
        except Exception as e:
            return f"❌ JSON parsing error: {e}\n\nExtracted JSON:\n{json_string}"
    else:
        return f"❌ Could not find JSON in response.\n\nRaw response:\n{raw_text}"
