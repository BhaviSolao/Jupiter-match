from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
import pdfplumber
from docx import Document
import os

# ---------- CONFIG ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Jupiter – Resume & Job Matcher")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- CONSTANTS ----------
KNOWN_SKILLS = {
    "python","sql","machine learning","deep learning","statistics",
    "regression","classification","clustering","eda",
    "pandas","numpy","matplotlib","seaborn","scikit-learn",
    "tensorflow","pytorch","power bi","tableau","excel",
    "spark","pyspark","aws","gcp","azure"
}

# ---------- HELPERS ----------
def extract_text(file: UploadFile):
    text = ""

    if file.filename.endswith(".pdf"):
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

    elif file.filename.endswith(".docx"):
        doc = Document(file.file)
        for para in doc.paragraphs:
            text += para.text + "\n"

    return text.lower().strip()


def extract_skills(text: str):
    found = set()
    for skill in KNOWN_SKILLS:
        if skill in text:
            found.add(skill)
    return found


def ats_score(matched, total):
    if total == 0:
        return 0, "No skills detected"

    percent = (matched / total) * 100

    if percent >= 70:
        return 10, "Good"
    elif percent >= 40:
        return 6, "Medium"
    else:
        return 2, "Poor"


# ---------- UI ----------
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return open("templates/index.html").read()


# ---------- ANALYZE JOB ----------
@app.post("/analyze-job")
async def analyze_job(file: UploadFile = File(...)):
    jd_text = extract_text(file)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an ATS job description analyzer. "
                    "Return clean plain text only. Do NOT use Markdown or **."
                )
            },
            {
                "role": "user",
                "content": f"""
From the job description below, extract:

Required Skills (comma-separated)
Preferred Skills (comma-separated, if any)
Years of Experience Required (mention number if stated, otherwise say 'Not specified')
Key Responsibilities (3 short bullet points in plain text)

Job Description:
{jd_text}
"""
            }
        ]
    )

    return {
        "type": "job_analysis",
        "analysis": response.choices[0].message.content.strip()
    }


# ---------- ANALYZE RESUME ----------
@app.post("/analyze-resume")
async def analyze_resume(file: UploadFile = File(...)):
    resume_text = extract_text(file)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an ATS resume reviewer. "
                    "Return clean plain text only. Do NOT use Markdown or **."
                )
            },
            {
                "role": "user",
                "content": f"""
Analyze this resume and return:

3 strongest skills
3 weaknesses
3 improvement suggestions

Resume:
{resume_text}
"""
            }
        ]
    )

    return {
        "type": "resume_analysis",
        "analysis": response.choices[0].message.content.strip()
    }


# ---------- MATCH JOB & RESUME (UPDATED AS REQUESTED) ----------
@app.post("/match-job-resume")
async def match_job_resume(
    job_file: UploadFile = File(...),
    resume_file: UploadFile = File(...)
):
    jd_text = extract_text(job_file)
    resume_text = extract_text(resume_file)

    jd_skills = extract_skills(jd_text)
    resume_skills = extract_skills(resume_text)

    matched = jd_skills.intersection(resume_skills)
    missing = jd_skills - matched

    score, label = ats_score(len(matched), len(jd_skills))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an ATS career advisor. "
                    "Return clean plain text only. Do NOT use Markdown or **."
                )
            },
            {
                "role": "user",
                "content": f"""
The following skills are required by the job but missing from the resume:
{', '.join(sorted(missing))}

The following skills already match:
{', '.join(sorted(matched))}

Give 3 clear, actionable suggestions to improve the resume so that it better matches the job description.
Focus on:
- skills to learn or highlight
- tools or techniques to add
- experience or projects to emphasize
"""
            }
        ]
    )

    return {
        "type": "ats_match",
        "ats_score": score,
        "label": label,
        "matched_skills": sorted(list(matched)),
        "missing_skills": sorted(list(missing)),
        "feedback": response.choices[0].message.content.strip()
    }
