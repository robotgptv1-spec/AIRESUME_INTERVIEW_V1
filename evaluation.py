"""
Resume vs JD match scoring - TF-IDF cosine similarity + regex based skill extraction.
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Common tech skills / keywords dictionary - extend as needed
SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "php", "ruby",
    "react", "angular", "vue", "next.js", "node.js", "express", "flask", "django", "fastapi",
    "html", "css", "tailwind", "bootstrap",
    "sql", "mysql", "postgresql", "mongodb", "redis", "firebase", "sqlite",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "jenkins",
    "git", "github", "gitlab", "linux", "bash",
    "machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch",
    "scikit-learn", "pandas", "numpy", "keras", "opencv", "llm", "rag", "faiss", "langchain",
    "rest api", "graphql", "microservices", "agile", "scrum",
    "data structures", "algorithms", "system design", "oop",
]


def extract_skills(text: str) -> set:
    text_lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return found


def compute_match(resume_text: str, jd_text: str) -> dict:
    """TF-IDF cosine similarity ke liye overall score + skill-level gap analysis."""
    # 1. Overall semantic similarity via TF-IDF
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

    # 2. Skill-level keyword matching
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched_skills = sorted(resume_skills & jd_skills)
    missing_skills = sorted(jd_skills - resume_skills)
    extra_skills = sorted(resume_skills - jd_skills)

    # 3. Weighted overall score: 60% semantic similarity + 40% skill coverage
    skill_coverage = len(matched_skills) / len(jd_skills) if jd_skills else 1.0
    overall_score = round((0.6 * similarity + 0.4 * skill_coverage) * 100, 1)

    return {
        "overall_score": float(overall_score),
        "semantic_similarity": float(round(similarity * 100, 1)),
        "skill_coverage": float(round(skill_coverage * 100, 1)),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "extra_skills": extra_skills,
    }
