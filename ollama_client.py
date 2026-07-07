"""
Ollama client wrapper - Gemini ki jagah local Ollama model use karta hai.
Requirements: Ollama installed + running (https://ollama.com)
Run once: `ollama pull llama3.2:3b`  (ya phi3 / mistral, apke VRAM ke hisaab se)
"""
import requests
import json

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"   # 4-6GB VRAM ke liye best balance. Halka chahiye toh "phi3"


class OllamaError(Exception):
    pass


def is_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Ollama se connect nahi ho paya: {e}")


def generate_content(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.7) -> str:
    """Gemini ke generate_content() jaisa hi interface - drop-in replacement."""
    if not is_ollama_running():
        raise OllamaError(
            "Ollama nahi chal raha! Terminal mein 'ollama serve' run karo, "
            "aur model pull karo: 'ollama pull llama3.2:3b'"
        )
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Ollama request fail hui: {e}")


def generate_json(prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """Structured JSON output ke liye - format='json' use karta hai."""
    if not is_ollama_running():
        raise OllamaError("Ollama nahi chal raha! 'ollama serve' run karo pehle.")
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.4},
            },
            timeout=180,
        )
        response.raise_for_status()
        raw = response.json().get("response", "{}")
        return json.loads(raw)
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        raise OllamaError(f"Ollama JSON response parse nahi hui: {e}")
