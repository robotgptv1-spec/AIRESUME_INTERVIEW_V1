"""
AI Interview Prep App - Flask Backend
Resume + JD upload -> Skill gap analysis -> Mock interview (Ollama) -> Final report
"""
import os
import uuid
import re
from flask import Flask, request, jsonify, render_template, session, send_file
from werkzeug.utils import secure_filename
import io

from services.parser import load_file
from services.evaluation import compute_match
from services.ollama_client import generate_content, is_ollama_running, list_models, OllamaError

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory session store: { session_id: InterviewSession }
SESSIONS = {}

DIFFICULTY_GUIDANCE = {
    "fresher": "Beginner-friendly sawal poochho, fundamentals aur basic project understanding pe focus karo.",
    "mid": "Intermediate-level depth rakho, real-world implementation aur trade-offs pe sawal poochho.",
    "senior": "Advanced/architectural sawal poochho, system design, scalability aur decision-making test karo.",
}


class InterviewSession:
    def __init__(self, resume_path, jd_path, difficulty="mid"):
        self.resume_path = resume_path
        self.jd_path = jd_path
        self.difficulty = difficulty
        self.resume_text = ""
        self.jd_text = ""
        self.match_metrics = {}
        self.questions = []
        self.user_answers = {}
        self.answer_feedback = {}

    def start_screening(self):
        self.resume_text = load_file(self.resume_path)
        self.jd_text = load_file(self.jd_path)

        if not self.resume_text.strip() or not self.jd_text.strip():
            raise ValueError("Resume ya JD file se text extract nahi ho paya!")

        self.match_metrics = compute_match(self.resume_text, self.jd_text)
        return self.match_metrics

    def generate_interview_questions(self, num_questions=5):
        guidance = DIFFICULTY_GUIDANCE.get(self.difficulty, DIFFICULTY_GUIDANCE["mid"])
        prompt = f"""Aap ek senior technical interviewer hain. Candidate ka interview lena hai.

Difficulty level: {self.difficulty.upper()} - {guidance}

Mera Target:
1. Candidate ke core projects aur skills ko test karein.
2. Jo skills Job Description mein zaroori hain par candidate ke resume mein missing hain
   ({', '.join(self.match_metrics.get('missing_skills', [])[:8]) or 'koi major gap nahi'}),
   unpar ek sawal poochhein taaki pata chale unhe basic knowledge hai ya nahi.

RESUME TEXT:
{self.resume_text[:4000]}

JOB DESCRIPTION:
{self.jd_text[:4000]}

Output format - bahut zaroori hai isse exactly follow karna:
Sirf {num_questions} numbered questions likho, kuch aur mat likhna.
Koi intro line mat likhna (jaise "Yahan sawal hain:" ya "Aapka sawal ye raha hai:").
Koi outro line mat likhna.
Har line sirf "1. <question>" jaise format mein honi chahiye, number ke saath shuru.
Pehli line seedha "1." se shuru honi chahiye.
"""
        response_text = generate_content(prompt)
        raw_questions = response_text.strip().split("\n")
        cleaned = []
        for q in raw_questions:
            q = q.strip()
            match = re.match(r"^\d+[\.\)]\s*(.+)", q)
            if match:
                question_text = match.group(1).strip()
                if question_text:
                    cleaned.append(question_text)

        # Fallback: agar model ne numbering follow nahi ki, toh non-empty
        # lines use karo jo kam se kam ek question jaisi lagti hain (? ke saath ya lambi line)
        if not cleaned:
            for q in raw_questions:
                q = q.strip()
                if q and ("?" in q or len(q) > 25):
                    cleaned.append(q)

        self.questions = cleaned[:num_questions]
        if not self.questions:
            raise OllamaError(
                "Model se koi valid question extract nahi hua. Ollama model shayad instructions "
                "follow nahi kar raha - dobara try karo ya model badal ke dekho (llama3.2:3b recommended)."
            )
        return self.questions

    def score_answer(self, idx: int, answer: str):
        """Har answer ke baad turant ek quick feedback + score dena (naya feature)."""
        question = self.questions[idx]
        prompt = f"""Aap ek technical interviewer hain. Neeche ek interview question aur candidate ka answer diya gaya hai.

Question: {question}
Candidate Answer: {answer}

Sirf ye format follow karo, kuch aur mat likho:
SCORE: <0 se 10 ke beech ek number>
FEEDBACK: <candidate ke answer par ek chhota (max 2 line) constructive feedback, Hinglish mein>
"""
        response_text = generate_content(prompt, temperature=0.4)
        score_match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", response_text)
        feedback_match = re.search(r"FEEDBACK:\s*(.+)", response_text, re.DOTALL)
        score = float(score_match.group(1)) if score_match else None
        feedback = feedback_match.group(1).strip() if feedback_match else response_text
        return {"score": score, "feedback": feedback}

    def generate_final_review(self):
        interview_transcript = ""
        for i, q in enumerate(self.questions):
            ans = self.user_answers.get(i, "No Answer Provided")
            fb = self.answer_feedback.get(i, {})
            interview_transcript += (
                f"Question {i+1}: {q}\nCandidate Answer: {ans}\n"
                f"Per-answer Score: {fb.get('score', 'N/A')}/10\n\n"
            )

        prompt = f"""Aap ek Technical Hiring Manager hain. Candidate ka final review report taiyar karna hai
based on their resume, the job description, and their answers during the interview.

CANDIDATE INITIAL MATCH SCORE: {self.match_metrics['overall_score']}%
MATCHED SKILLS: {', '.join(self.match_metrics['matched_skills'])}
MISSING SKILLS: {', '.join(self.match_metrics['missing_skills'])}

INTERVIEW TRANSCRIPT:
{interview_transcript}

Please provide a structured final review in this exact format:
STRENGTHS: <candidate ne kin questions ka jawab accha diya aur resume ke strong points>
WEAKNESSES: <kahan par candidate weak laga ya answer adhoora tha>
VERDICT: <ek line mein: Strong Hire / Hire / Borderline / Reject + reason>
"""
        response_text = generate_content(prompt, temperature=0.5)
        return response_text


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session() -> InterviewSession:
    sid = session.get("sid")
    if not sid or sid not in SESSIONS:
        raise ValueError("Session expired ya invalid hai. Pehle resume/JD upload karo.")
    return SESSIONS[sid]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "ollama_running": is_ollama_running(),
        "models": list_models() if is_ollama_running() else [],
    })


@app.route("/api/upload", methods=["POST"])
def upload():
    resume_file = request.files.get("resume")
    jd_file = request.files.get("jd")
    difficulty = request.form.get("difficulty", "mid")

    if not resume_file or not jd_file:
        return jsonify({"error": "Resume aur JD dono files chahiye"}), 400
    if not (allowed_file(resume_file.filename) and allowed_file(jd_file.filename)):
        return jsonify({"error": "Sirf PDF, DOCX, ya TXT files allowed hai"}), 400

    sid = str(uuid.uuid4())
    session["sid"] = sid

    resume_path = os.path.join(UPLOAD_FOLDER, f"{sid}_resume_{secure_filename(resume_file.filename)}")
    jd_path = os.path.join(UPLOAD_FOLDER, f"{sid}_jd_{secure_filename(jd_file.filename)}")
    resume_file.save(resume_path)
    jd_file.save(jd_path)

    interview_session = InterviewSession(resume_path, jd_path, difficulty=difficulty)
    SESSIONS[sid] = interview_session

    try:
        metrics = interview_session.start_screening()
        return jsonify({"success": True, "metrics": metrics})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/api/questions", methods=["POST"])
def questions():
    try:
        interview_session = get_session()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    num_questions = int(request.json.get("num_questions", 5)) if request.is_json else 5
    try:
        qs = interview_session.generate_interview_questions(num_questions=num_questions)
        return jsonify({"success": True, "questions": qs})
    except OllamaError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/api/answer", methods=["POST"])
def answer():
    try:
        interview_session = get_session()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.json
    idx = int(data.get("index"))
    ans_text = data.get("answer", "")
    interview_session.user_answers[idx] = ans_text

    try:
        feedback = interview_session.score_answer(idx, ans_text)
        interview_session.answer_feedback[idx] = feedback
        return jsonify({"success": True, "feedback": feedback})
    except OllamaError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/api/report", methods=["POST"])
def report():
    try:
        interview_session = get_session()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        final_report = interview_session.generate_final_review()
        avg_score = (
            sum(f["score"] for f in interview_session.answer_feedback.values() if f.get("score") is not None)
            / max(len(interview_session.answer_feedback), 1)
        )
        return jsonify({
            "success": True,
            "report": final_report,
            "avg_answer_score": round(avg_score, 1),
            "match_metrics": interview_session.match_metrics,
        })
    except OllamaError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/api/report/download", methods=["GET"])
def download_report():
    try:
        interview_session = get_session()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    lines = ["# Interview Report\n"]
    lines.append(f"**Overall Match Score:** {interview_session.match_metrics.get('overall_score')}%\n")
    for i, q in enumerate(interview_session.questions):
        ans = interview_session.user_answers.get(i, "N/A")
        fb = interview_session.answer_feedback.get(i, {})
        lines.append(f"### Q{i+1}: {q}\n**Answer:** {ans}\n**Score:** {fb.get('score', 'N/A')}/10\n**Feedback:** {fb.get('feedback', '')}\n")

    report_text = interview_session.generate_final_review()
    lines.append(f"\n## Final Review\n{report_text}")

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.seek(0)
    return send_file(buf, mimetype="text/markdown", as_attachment=True, download_name="interview_report.md")


if __name__ == "__main__":
    app.run(debug=True, port=5000)