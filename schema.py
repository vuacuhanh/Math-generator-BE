from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, model_validator

Operation = Literal["+", "-", "×", "÷"]
Mode = Literal["easy_to_hard", "balanced", "hard_to_easy"] 
class GenerationConfig(BaseModel):
    grade: int = Field(ge=1, le=5)
    operations: List[Operation]
    count: int = Field(ge=1, le=200)
    mcq_count: Optional[int] = None     
    word_count: Optional[int] = None   
    min_value: int = Field(ge=0)
    max_value: int = Field(ge=1)
    include_word_problems: bool = False
    include_distractors: bool = True
    seed: Optional[int] = None
    language: Literal["vi", "en"] = "vi"


    @model_validator(mode="after")
    def _check_counts(self):
        wc = self.word_count or 0
        mcq = self.mcq_count or 0
        if wc > self.count:
            raise ValueError("word_count must be <= count")
        if mcq > self.count - wc:
            raise ValueError("mcq_count must be <= count - word_count")
        return self


class Problem(BaseModel):
    id: int
    text: str
    answer: str
    distractors: List[str] = []
    kind: Literal["arithmetic", "word"] = "arithmetic"
    difficulty: float = 0.0
    source: Optional[str] = None

class AssembleRequest(BaseModel):
    pool: List[Problem]
    total_count: int = 20
    mcq_count: int = 10
    word_count: int = 0
    mode: Literal["easy_to_hard", "balanced", "hard_to_easy"] = "easy_to_hard"

class Evaluation(BaseModel):
    avg_difficulty: float
    buckets: Dict[str, int]
    by_kind: Dict[str, int]
    by_op: Dict[str, int]
    notes: List[str] = []
