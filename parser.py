import os
import pdfplumber
import docx


def load_file(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return _parse_pdf(filepath)
    elif ext == ".docx":
        return _parse_docx(filepath)
    elif ext == ".txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}. Sirf .pdf, .docx, .txt allowed hai.")


def _parse_pdf(filepath: str) -> str:
    text_parts = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        raise ValueError(
            f"Ye ek valid PDF file nahi hai ya corrupt hai ({e}). "
            f"Real PDF export karke dobara try karo (plain text file ka naam .pdf rakh dena kaam nahi karega)."
        )
    text = "\n".join(text_parts)
    if not text.strip():
        raise ValueError(
            "PDF se text extract nahi hua - ho sakta hai ye scanned image PDF ho (OCR chahiye)."
        )
    return text


def _parse_docx(filepath: str) -> str:
    document = docx.Document(filepath)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)