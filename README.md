# InterviewIQ — AI Mock Interview App

Resume + JD upload → skill-gap screening → AI mock interview → final hiring report.
Runs fully **local** using **Ollama** (no API key, no cost, no internet needed for inference).

## 1. Install Ollama

Download from https://ollama.com and install it. Then pull a model that fits your
GPU (4–6GB VRAM friendly options, smallest → biggest):

```bash
ollama pull phi3          # fastest, lowest VRAM
ollama pull llama3.2:3b   # good balance (default used in this app)
ollama pull mistral:7b    # best quality, needs more VRAM
```

Start the Ollama server (usually auto-starts on install, otherwise):
```bash
ollama serve
```

If you pick a model other than `llama3.2:3b`, update `DEFAULT_MODEL` in
`services/ollama_client.py`.

## 2. Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 3. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

## Project structure

```
interview_app/
├── app.py                     # Flask routes + InterviewSession logic
├── services/
│   ├── parser.py               # PDF/DOCX/TXT text extraction
│   ├── evaluation.py           # TF-IDF + skill-keyword match scoring
│   └── ollama_client.py        # Local Ollama wrapper (replaces Gemini)
├── templates/index.html        # Single-page glassmorphic UI
├── static/css/style.css
├── static/js/app.js             # Upload, voice input, timer, live scoring
└── uploads/                     # Uploaded resume/JD files (gitignored)
```

## Features

- 📄 Resume + JD upload (PDF / DOCX / TXT)
- 🎯 TF-IDF + skill-keyword fitment scoring with animated radar reveal
- 🎚️ Difficulty selector — Fresher / Mid-level / Senior — changes question depth
- 🤖 AI-generated interview questions tailored to resume gaps
- 🎙️ Voice-to-text answers (Web Speech API, no backend cost)
- ⏱️ Per-question timer
- ✅ Instant per-answer score + feedback (not just a final report)
- 📊 Final hiring verdict report (Strengths / Weaknesses / Verdict)
- ⬇️ Downloadable Markdown report

## Note on Vercel deployment

Vercel is serverless and **cannot run Ollama** (Ollama needs a persistent local
process with GPU/CPU access). To deploy publicly, options are:
1. Deploy just the frontend to Vercel, and point it at an Ollama backend you
   host yourself on a VPS (Railway, Render, a home server, etc.), or
2. Swap `services/ollama_client.py` back to a hosted API (Gemini/OpenAI) for
   the deployed version, keeping Ollama for local development.

## Security note

Never hardcode API keys in source files (the original `app.py` had a Gemini
key hardcoded — remove/rotate that key if it was ever pushed to GitHub).
Use a `.env` file + `python-dotenv` if you add a hosted LLM back in.
