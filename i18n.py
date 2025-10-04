from schema import GenerationConfig

def build_prompt(cfg: GenerationConfig, n: int) -> str:
    ops = ", ".join(cfg.operations)
    if cfg.language == "vi":
        return f"""
Bạn là giáo viên tiểu học. Hãy tạo {n} bài toán có lời văn 1–2 câu
cho học sinh lớp {cfg.grade}, chỉ dùng các phép {ops} trong phạm vi {cfg.min_value} đến {cfg.max_value}.
Trả về JSON: {{ "items": [{{"text":"...", "answer":"..."}}] }}
- Không kèm lời giải, chỉ đáp án số.
- Chủ đề đời sống an toàn (táo, bút, kẹo, thú cưng...).
"""
    else:
        return f"""
You are a primary school teacher. Create {n} short word problems
for grade {cfg.grade} using operations {ops}, with values {cfg.min_value}..{cfg.max_value}.
Return JSON: {{ "items": [{{"text":"...", "answer":"..."}}] }}
- No reasoning, numeric answer only.
- Safe, age-appropriate topics.
"""
