# backend/pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from pathlib import Path
from typing import List
from schema import Problem

def _register_font():
    try:
        here = Path(__file__).resolve().parent
        candidates = [
            here / "fonts" / "Roboto-VariableFont_wdth,wght.ttf",  # ưu tiên font nằm trong repo
            here / "fonts" / "DejaVuSans.ttf",                     
        ]
        for p in candidates:
            if p.exists():
                pdfmetrics.registerFont(TTFont("VN", str(p)))
                return "VN"
    except Exception as e:
        print("Font register failed:", e)
    return "Helvetica"  # fallback (sẽ thiếu dấu tiếng Việt)

FONT_NAME = _register_font()

def render_pdf(path: str, title: str, problems: List[Problem], with_answers: bool=False):
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4
    margin = 15 * mm
    lh = 8 * mm
    x = margin
    y = H - margin

    c.setFont(FONT_NAME, 14)
    c.drawString(x, y, title)
    y -= 1.5 * lh
    c.setFont(FONT_NAME, 11)

    max_width = W - 2 * margin  # ✅ BỔ SUNG

    for p in problems:
        # Dòng câu hỏi (+ đáp án nếu with_answers)
        line = f"{p.id}. {p.text}"
        if with_answers and getattr(p, "answer", None):
            line += f"   Đáp án: {p.answer}"

        for seg in simpleSplit(line, FONT_NAME, 11, max_width):
            if y < margin + lh:
                c.showPage(); y = H - margin; c.setFont(FONT_NAME, 11)
            c.drawString(x, y, seg); y -= lh

        # In các lựa chọn trắc nghiệm nếu có (A/B/C/D), B là đúng (khớp UI)
        if getattr(p, "distractors", None) and len(p.distractors) >= 3 and getattr(p, "answer", None):
            options = [
                ("A", p.distractors[0]),
                ("B", p.answer),
                ("C", p.distractors[1]),
                ("D", p.distractors[2]),
            ]
            c.setFont(FONT_NAME, 10)
            indent = 8 * mm
            for lab, txt in options:
                for seg in simpleSplit(f"{lab}) {txt}", FONT_NAME, 10, max_width - indent):
                    if y < margin + lh:
                        c.showPage(); y = H - margin; c.setFont(FONT_NAME, 10)
                    c.drawString(x + indent, y, seg); y -= lh
            c.setFont(FONT_NAME, 11)

        y -= 0.5 * lh

    c.save()
