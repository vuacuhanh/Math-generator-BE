# main.py
import os
import io
import re
import csv
import tempfile
from typing import List

from fastapi import FastAPI, Response, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from schema import GenerationConfig, Problem, AssembleRequest, Evaluation
from generator import (
    generate_arithmetic,
    make_distractors,
    assemble_exam,
    evaluate_exam,
    score_problem,
)
from ai_provider import generate_word_problems
from pdf import render_pdf


# ======================
# C O R S   S E T U P
# ======================
# Ví dụ trên Railway:
#   ALLOWED_ORIGINS="http://localhost:3000,https://math-generator-tau.vercel.app"
ALLOWED = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

app = FastAPI(title="AI Math Problem Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,                      # cho phép danh sách cụ thể
    allow_origin_regex=r"https://.*\.vercel\.app$",  # + mọi subdomain vercel.app (preview/prod)
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,                    # để True nếu cần gửi cookie/Authorization kèm credentials
    max_age=86400,
)


# ======================
# H E A L T H   C H E C K
# ======================
@app.get("/")
def root():
    return {"status": "ok", "service": "math-backend"}

@app.get("/api/health")
def health():
    return {"ok": True}


# ======================
# H E L P E R S
# ======================
def _build_problems(cfg: GenerationConfig) -> List[Problem]:
    """
    Sinh đề theo cấu hình:
    - count: tổng số câu
    - word_count: số câu lời văn (nếu None thì tự suy từ include_word_problems)
    - include_distractors: thêm lựa chọn nhiễu cho câu số học
    """
    total = cfg.count
    target_word = (
        cfg.word_count if cfg.word_count is not None
        else (cfg.count // 3 if cfg.include_word_problems else 0)
    )
    target_word = max(0, min(total, target_word))
    target_mcq = total - target_word

    # 1) Sinh câu số học
    arith_cfg = cfg.model_copy(update={"count": target_mcq})
    problems = generate_arithmetic(arith_cfg)

    # 2) Sinh câu lời văn
    if target_word > 0:
        pairs = generate_word_problems(cfg, target_word)  # List[Tuple[q, a]]
        start = len(problems) + 1
        for idx, (q, a) in enumerate(pairs, start=start):
            problems.append(Problem(id=idx, text=q, answer=a, kind="word"))

    # 3) Thêm distractors nếu bật
    if cfg.include_distractors:
        for p in problems:
            if p.kind == "arithmetic":
                p.distractors = make_distractors(p.answer)

    # 4) Đánh số lại id
    for i, p in enumerate(problems, start=1):
        p.id = i

    return problems


def _parse_uploaded_text(data: str) -> List[Problem]:
    """
    Parse .txt/.csv đơn giản:
    - Hỗ trợ phân tách bằng '|' hoặc ',' hoặc '... đáp án: ...'
    """
    out: List[Problem] = []
    lines = [l.strip() for l in data.splitlines() if l.strip()]

    if any(("," in l) or ("|" in l) for l in lines):
        reader = csv.reader(io.StringIO("\n".join(lines)), delimiter="|")
        for i, row in enumerate(reader, start=1):
            if len(row) == 1:
                row = next(csv.reader([row[0]], delimiter=","))  # fallback dấu ','
            if not row:
                continue
            q = row[0].strip()
            a = row[1].strip() if len(row) > 1 else ""
            kind = "arithmetic" if re.search(r"[+\-×÷]", q) else "word"
            out.append(Problem(id=i, text=q, answer=a, kind=kind, source="uploaded"))
    else:
        for i, l in enumerate(lines, start=1):
            m = re.split(r"đáp án[:：]|answer[:：]", l, flags=re.I)
            q = m[0].strip()
            a = m[1].strip() if len(m) > 1 else ""
            kind = "arithmetic" if re.search(r"[+\-×÷]", q) else "word"
            out.append(Problem(id=i, text=q, answer=a, kind=kind, source="uploaded"))

    return out


# ======================
# A P I   R O U T E S
# ======================

@app.post("/api/generate", response_model=List[Problem])
def api_generate(cfg: GenerationConfig) -> List[Problem]:
    return _build_problems(cfg)


@app.post("/api/export/questions")
def api_export_questions(cfg: GenerationConfig):
    problems = _build_problems(cfg)
    fd, path = tempfile.mkstemp(suffix="_questions.pdf")
    os.close(fd)
    render_pdf(path, "BÀI TẬP TOÁN - CÂU HỎI", problems, with_answers=False)
    try:
        with open(path, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=worksheet_questions.pdf"},
    )


@app.post("/api/export/answers")
def api_export_answers(cfg: GenerationConfig):
    problems = _build_problems(cfg)
    fd, path = tempfile.mkstemp(suffix="_answers.pdf")
    os.close(fd)
    render_pdf(path, "BÀI TẬP TOÁN - ĐÁP ÁN", problems, with_answers=True)
    try:
        with open(path, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=worksheet_answers.pdf"},
    )


@app.post("/api/upload", response_model=List[Problem])
async def api_upload(file: UploadFile = File(...)) -> List[Problem]:
    if file.content_type not in (
        "text/plain",
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",  # một số trình duyệt gửi vậy cho .txt
    ):
        raise HTTPException(400, "Hiện hỗ trợ .txt, .csv")

    raw = (await file.read()).decode("utf-8", errors="ignore")
    problems = _parse_uploaded_text(raw)
    for p in problems:
        p.difficulty = score_problem(p)
    return problems


@app.post("/api/assemble", response_model=List[Problem])
def api_assemble(req: AssembleRequest) -> List[Problem]:
    return assemble_exam(req.pool, req.total_count, req.mcq_count, req.word_count, req.mode)


@app.post("/api/evaluate", response_model=Evaluation)
def api_evaluate(problems: List[Problem]) -> Evaluation:
    return evaluate_exam(problems)
