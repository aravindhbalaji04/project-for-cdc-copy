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

### Scoring Rubric:
[Keep rubric unchanged - same as you provided]

### VERY IMPORTANT: OUTPUT INSTRUCTIONS
Respond with *only* a valid JSON object. No markdown, no preface. The JSON must exactly match this structure and include all subsection scores and comments.

### REQUIRED JSON FORMAT:
{
  "scores": {
    "Skill_Alignment": {
      "score": X,
      "subsections": {
        "required_skills": {"score": X/100, "comment": "..."},
        "certifications": {"score": X/100, "comment": "..."},
        "bonus_certifications": {"bonus": X, "comment": "..."}
      }
    },
    "Experience_Relevance": {
      "score": X,
      "subsections": {
        "role_match": {"score": X/50, "comment": "..."},
        "tools_covered": {"score": X/50, "comment": "..."},
        "penalties": {"penalty": -X, "comment": "..."}
      }
    },
    "Internship_Quality": {
      "score": X,
      "subsections": {
        "duration_type": {"score": X/50, "comment": "..."},
        "impact": {"score": X/50, "comment": "..."},
        "innovation_bonus": {"bonus": +X, "comment": "..."},
        "penalties": {"penalty": -X, "comment": "..."}
      }
    },
    "Impactful_Contributions": {
      "score": X,
      "subsections": {
        "contribution_1": {"score": X/100, "comment": "..."},
        "contribution_2": {"score": X/100, "comment": "..."}
      }
    },
    "Soft_Skills": {
      "score": X,
      "subsections": {
        "communication": {"score": X/25, "comment": "..."},
        "teamwork": {"score": X/25, "comment": "..."},
        "leadership": {"score": X/25, "comment": "..."},
        "mentoring": {"score": X/25, "comment": "..."}
      }
    },
    "Miscellaneous_Score": {
      "score": X,
      "subsections": {
        "grammar": {"score": X/100, "comment": "..."},
        "buzzwords": {"score": X/100, "comment": "..."},
        "active_voice": {"score": X/100, "comment": "..."},
        "repetition": {"score": X/100, "comment": "..."}
      }
    },
    "Format_Score": {
      "score": X,
      "subsections": {
        "structure": {"score": X/100, "comment": "..."},
        "font/layout": {"score": X/100, "comment": "..."},
        "readability": {"score": X/100, "comment": "..."}
      }
    },
    "weighted_total": X
  },
  "evaluation": "Brief summary of strengths and major areas for improvement"
}

Now evaluate the following resume content:
""" + f"\n\n{parsed_output}\n\nFormat_score = {format_score}"

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.0, top_p=1.0, top_k=1)
    )
    raw_text = response.text.strip()
    try:
        data = json.loads(raw_text)
        print(json.dumps(data, indent=2))
        return data["scores"]["weighted_total"]
    except Exception:
        pass
    try:
        # Use a simpler regex to find the first JSON object in the response
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            json_string = json_match.group(0)
            data = json.loads(json_string)
            print(json.dumps(data, indent=2))
            return data["scores"]["weighted_total"]
        else:
            return f"❌ JSON not detected.\n\nRaw response:\n{raw_text}"
    except Exception as e:
        return f"❌ JSON parsing failed: {e}\n\nRaw:\n{raw_text}"