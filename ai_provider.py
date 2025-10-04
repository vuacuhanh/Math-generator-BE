import os, json
from typing import List, Tuple
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
from schema import GenerationConfig
from i18n import build_prompt

# Nạp .env cùng thư mục backend
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

def generate_word_problems(cfg: GenerationConfig, n: int) -> List[Tuple[str, str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Fallback nội bộ: tạo n câu đơn giản + đáp án số
        import random
        random.seed(cfg.seed or 42)
        items: List[Tuple[str, str]] = []
        for _ in range(n):
            a = random.randint(cfg.min_value, cfg.max_value)
            b = random.randint(cfg.min_value, cfg.max_value)
            op = random.choice(cfg.operations or ["+","-","×","÷"])
            if op == "+":
                text, ans = f"Bạn Nam có {a} viên bi, mẹ cho thêm {b} viên. Hỏi Nam có tất cả bao nhiêu viên bi?", str(a+b)
            elif op == "-":
                a, b = max(a,b), min(a,b)
                text, ans = f"Có {a} quả cam, ăn bớt {b} quả. Còn lại bao nhiêu quả cam?", str(a-b)
            elif op == "×":
                text, ans = f"Mỗi hộp có {a} cái bút. Có {b} hộp như thế. Hỏi có tất cả bao nhiêu cái bút?", str(a*b)
            else:  # ÷
                b = max(1, b)
                t = a * b
                text, ans = f"Có {t} cái kẹo chia đều cho {b} bạn. Mỗi bạn được bao nhiêu cái kẹo?", str(a)
            items.append((text, ans))
        return items
    
    client = OpenAI(api_key=api_key)
    prompt = build_prompt(cfg, n)
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.6,
    )

    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    items = data.get("items", [])[:n]
    return [(str(it.get("text","")).strip(), str(it.get("answer","")).strip()) for it in items]
