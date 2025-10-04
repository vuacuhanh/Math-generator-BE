import os, io, csv, re, tempfile
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



ALLOWED = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="AI Math Problem Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_problems(cfg: GenerationConfig) -> List[Problem]:
    # quyết định số lượng theo tham số mới
    total = cfg.count
    target_word = cfg.word_count if cfg.word_count is not None else (cfg.count // 3 if cfg.include_word_problems else 0)
    target_word = max(0, min(total, target_word))
    target_mcq = total - target_word

    # 1) sinh số học đúng target_mcq
    arith_cfg = cfg.model_copy(update={"count": target_mcq})
    problems = generate_arithmetic(arith_cfg)

    # 2) sinh lời văn đúng target_word
    if target_word > 0:
        pairs = generate_word_problems(cfg, target_word)
        start = len(problems) + 1
        for idx, (q, a) in enumerate(pairs, start=start):
            problems.append(Problem(id=idx, text=q, answer=a, kind="word"))

    # 3) distractors cho bài số học nếu bật
    if cfg.include_distractors:
        for p in problems:
            if p.kind == "arithmetic":
                p.distractors = make_distractors(p.answer)

    # 4) đánh số lại
    for i, p in enumerate(problems, start=1):
        p.id = i
    return problems

# --- helper: parse file .txt/.csv ---
def _parse_uploaded_text(data: str) -> List[Problem]:
    out: List[Problem] = []
    lines = [l.strip() for l in data.splitlines() if l.strip()]
    if any(("," in l) or ("|" in l) for l in lines):
        reader = csv.reader(io.StringIO("\n".join(lines)), delimiter="|")
        for i, row in enumerate(reader, start=1):
            if len(row) == 1:
                row = next(csv.reader([row[0]], delimiter=","))
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

@app.post("/api/generate", response_model=List[Problem])
def generate(cfg: GenerationConfig) -> List[Problem]:
    return _build_problems(cfg)

@app.post("/api/export/questions")
def export_questions(cfg: GenerationConfig):
    problems = _build_problems(cfg)
    fd, path = tempfile.mkstemp(suffix="_questions.pdf")
    os.close(fd)
    render_pdf(path, "BÀI TẬP TOÁN - CÂU HỎI", problems, with_answers=False)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=worksheet_questions.pdf"},
    )

@app.post("/api/export/answers")
def export_answers(cfg: GenerationConfig):
    problems = _build_problems(cfg)
    fd, path = tempfile.mkstemp(suffix="_answers.pdf")
    os.close(fd)
    render_pdf(path, "BÀI TẬP TOÁN - ĐÁP ÁN", problems, with_answers=True)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=worksheet_answers.pdf"},
    )

@app.post("/api/upload", response_model=List[Problem])
async def upload(file: UploadFile = File(...)) -> List[Problem]:
    if file.content_type not in ("text/plain", "text/csv", "application/vnd.ms-excel"):
        raise HTTPException(400, "Hiện hỗ trợ .txt, .csv")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    problems = _parse_uploaded_text(raw)
    for p in problems:
        p.difficulty = score_problem(p)
    return problems

@app.post("/api/assemble", response_model=List[Problem])
def assemble(req: AssembleRequest) -> List[Problem]:
    return assemble_exam(req.pool, req.total_count, req.mcq_count, req.word_count, req.mode)

@app.post("/api/evaluate", response_model=Evaluation)
def evaluate(problems: List[Problem]) -> Evaluation:
    return evaluate_exam(problems)
