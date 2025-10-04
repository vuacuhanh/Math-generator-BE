import random
import re
from typing import List
from collections import Counter
from statistics import mean

from schema import GenerationConfig, Problem, Operation, Evaluation, Mode

# -----------------
# Sinh toán số học
# -----------------
def generate_arithmetic(cfg: GenerationConfig) -> List[Problem]:
    if cfg.seed is not None:
        random.seed(cfg.seed)

    problems: List[Problem] = []
    ops: List[Operation] = list(cfg.operations)

    def pick_add() -> Problem:
        a = random.randint(cfg.min_value, cfg.max_value)
        b = random.randint(cfg.min_value, cfg.max_value)
        ans = a + b
        return Problem(id=0, text=f"{a} + {b} = ?", answer=str(ans), kind="arithmetic", source="generated")

    def pick_sub() -> Problem:
        a = random.randint(cfg.min_value, cfg.max_value)
        b = random.randint(cfg.min_value, cfg.max_value)
        if a < b:
            a, b = b, a
        ans = a - b
        return Problem(id=0, text=f"{a} - {b} = ?", answer=str(ans), kind="arithmetic", source="generated")

    def pick_mul() -> Problem:
        limit = 12 if cfg.grade <= 3 else cfg.max_value
        a = random.randint(cfg.min_value, min(limit, cfg.max_value))
        b = random.randint(cfg.min_value, min(limit, cfg.max_value))
        ans = a * b
        return Problem(id=0, text=f"{a} × {b} = ?", answer=str(ans), kind="arithmetic", source="generated")

    def pick_div() -> Problem:
        limit = max(1, min(12 if cfg.grade <= 3 else cfg.max_value, cfg.max_value))
        b = random.randint(max(1, cfg.min_value), max(1, limit))
        q = random.randint(cfg.min_value, max(cfg.min_value + 1, cfg.max_value))
        a = b * q
        return Problem(id=0, text=f"{a} ÷ {b} = ?", answer=str(q), kind="arithmetic", source="generated")

    pickers = {"+": pick_add, "-": pick_sub, "×": pick_mul, "÷": pick_div}

    for _ in range(cfg.count):
        op = random.choice(ops)
        p = pickers[op]()
        p.difficulty = score_arithmetic(p.text)  # chấm sơ bộ
        if cfg.include_distractors:
            p.distractors = make_distractors(p.answer)
        problems.append(p)

    for i, p in enumerate(problems, start=1):
        p.id = i
    return problems

# -----------------
# Chấm & đánh giá
# -----------------
def score_arithmetic(text: str) -> float:
    m = re.findall(r"(\d+)\s*([+\-×÷])\s*(\d+)", text)
    if not m:
        return 0.4
    a, op, b = m[0]
    a, b = int(a), int(b)
    base = {"+": 0.25, "-": 0.35, "×": 0.6, "÷": 0.75}[op]
    scale = min(1.0, (abs(a) + abs(b)) / 200.0)
    return max(0.0, min(1.0, base + 0.5 * scale))

def score_word(text: str) -> float:
    length = len(text)
    nums = len(re.findall(r"\d+", text))
    has_mult = "×" in text or "nhân" in text.lower() or "multiply" in text.lower()
    has_div  = "÷" in text or "chia" in text.lower() or "divide" in text.lower()
    base = 0.35 + 0.05 * nums + 0.0007 * length
    if has_mult: base += 0.12
    if has_div:  base += 0.18
    return max(0.0, min(1.0, base))

def score_problem(p: Problem) -> float:
    return score_arithmetic(p.text) if p.kind == "arithmetic" else score_word(p.text)

def _tag(v: float) -> str:
    return "easy" if v < 0.34 else "medium" if v < 0.67 else "hard"

def evaluate_exam(problems: List[Problem]) -> Evaluation:
    ds = [p.difficulty for p in problems if p.difficulty is not None]
    by_kind = Counter(p.kind for p in problems)
    by_op = Counter()
    for p in problems:
        m = re.findall(r"[+\-×÷]", p.text)
        if m:
            by_op[m[0]] += 1
    buckets = Counter(_tag(x) for x in ds)
    notes: List[str] = []
    if ds and mean(ds) > 0.7:
        notes.append("Đề hơi khó, cân nhắc tăng câu + hoặc -.")
    if by_kind.get("word", 0) == 0:
        notes.append("Chưa có bài toán lời văn.")

    return Evaluation(
        avg_difficulty=round(mean(ds), 3) if ds else 0.0,
        buckets=dict(buckets),
        by_kind=dict(by_kind),
        by_op=dict(by_op),
        notes=notes,
    )

def make_distractors(answer: str) -> List[str]:
    try:
        val = int(answer)
        cand = {val + 1, val - 1, val + 2, val - 2, max(0, val - 3)}
        cand.discard(val)
        out = [str(x) for x in sorted(cand, key=lambda _: random.random())][:3]
        while len(out) < 3:
            out.append(str(val + random.randint(4, 9)))
        return out[:3]
    except ValueError:
        base = ["Không xác định", "Chưa tính", "Thử lại"]
        out = [c for c in base if c != answer]
        while len(out) < 3:
            out.append(f"Phương án {len(out)+1}")
        return out[:3]

def assemble_exam(
    pool: List[Problem],
    total_count: int,
    mcq_count: int,
    word_count: int,
    mode: Mode,
) -> List[Problem]:
    # chấm nếu thiếu
    for p in pool:
        if p.difficulty is None or p.difficulty == 0:
            p.difficulty = score_problem(p)

    reverse = (mode == "hard_to_easy")
    pool_sorted = sorted(pool, key=lambda x: x.difficulty, reverse=reverse)

    if mode == "balanced":
        easies = [p for p in pool_sorted if _tag(p.difficulty) == "easy"]
        meds   = [p for p in pool_sorted if _tag(p.difficulty) == "medium"]
        hards  = [p for p in pool_sorted if _tag(p.difficulty) == "hard"]
        pool_sorted = []
        while (easies or meds or hards) and len(pool_sorted) < total_count:
            for bucket in (easies, meds, hards):
                if bucket and len(pool_sorted) < total_count:
                    pool_sorted.append(bucket.pop(0))

    words = [p for p in pool_sorted if p.kind == "word"]
    arith = [p for p in pool_sorted if p.kind == "arithmetic"]

    picked = words[:word_count] + arith[: (total_count - word_count)]

    have_mcq = sum(1 for p in picked if p.distractors)
    need = max(0, mcq_count - have_mcq)
    for p in picked:
        if need <= 0:
            break
        if p.kind == "arithmetic" and not p.distractors:
            p.distractors = make_distractors(p.answer)
            need -= 1

    picked = sorted(picked, key=lambda x: x.difficulty)
    for i, p in enumerate(picked, start=1):
        p.id = i
    return picked
