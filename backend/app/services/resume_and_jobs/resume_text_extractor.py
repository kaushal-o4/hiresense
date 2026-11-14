# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/resume_and_jobs/resume_text_extractor.py
#
# FILE PURPOSE:
# Extracts plain text from uploaded PDF and DOCX resumes.
#
# WHAT THIS FILE DOES:
# 1. detect_kind(): checks the file really is a PDF or DOCX.
# 2. extract_text(): returns the text.
# 3. Raises ResumeParseError for unsupported or unreadable files.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: detect_kind, extract_text
#
# IMPORTANT CLASSES:
#    - ResumeParseError
#
# IMPORTANT VARIABLES / SETTINGS:
#    PDF_TYPES, DOCX_TYPES
#
# INPUT:
# Uploaded file bytes, name and content type.
#
# OUTPUT:
# Resume text.
#
# FILES CONNECTED TO THIS FILE:
#    Used by: app/routers/student_portal_routes.py
#
# EXECUTION FLOW:
#    Upload
#       |
#       v
#    detect_kind()
#       |
#       v
#    extract_text()
#       |
#       v
#    Text sent to AI analysis
#
# IMPORTANT DEPENDENCIES:
#    docx, pypdf
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Extract plain text from uploaded PDF / DOCX resumes."""
import io

from docx import Document
from pypdf import PdfReader

PDF_TYPES = {"application/pdf"}
DOCX_TYPES = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


class ResumeParseError(ValueError):
    pass


def detect_kind(filename: str, content_type: str | None, data: bytes) -> str:
    name = filename.lower()
    if data[:4] == b"%PDF" and (name.endswith(".pdf") or content_type in PDF_TYPES):
        return "pdf"
    if data[:2] == b"PK" and (name.endswith(".docx") or content_type in DOCX_TYPES):
        return "docx"
    raise ResumeParseError("Only PDF and DOCX resumes are supported")


def extract_text(kind: str, data: bytes) -> str:
    try:
        if kind == "pdf":
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
    except Exception as exc:  # corrupted / encrypted files - don't echo library internals to the user
        raise ResumeParseError("Could not read the file. It may be corrupted or password-protected; "
                               "please export it again as a PDF or DOCX.") from exc
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = "\n".join(l for l in text.split("\n") if l.strip())
    if len(text.strip()) < 30:
        raise ResumeParseError("The resume appears to contain no readable text (scanned images are not supported)")
    return text[:60000]
