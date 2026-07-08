"""Task Profiler — deterministic heuristics, no learned prediction yet.

Classifies the task and proposes a context budget and retrieval depth.
The point is not perfect estimation; it is that DIFFERENT tasks get
DIFFERENT budgets, unlike fixed top-K RAG which treats every task the same.
"""

import re
from dataclasses import dataclass

# Words suggesting the answer spans multiple entities / dependency hops
_MULTI_HOP_MARKERS = re.compile(
    r"\b(affect|impact|break|depend|depends|dependency|change|changing|"
    r"propagate|downstream|upstream|ripple|consequence|if\s+i\s+)\b",
    re.IGNORECASE,
)
# Words suggesting a simple factual lookup
_FACTUAL_MARKERS = re.compile(
    r"^\s*(what|which|where|who|when|how\s+many|how\s+much|does|is|are)\b",
    re.IGNORECASE,
)
# Words suggesting structural/architecture questions
_STRUCTURAL_MARKERS = re.compile(
    r"\b(structure|architecture|calls?|imports?|inherits?|uses|defined|"
    r"implemented|located|contains?|list)\b",
    re.IGNORECASE,
)
# Code-symbol-looking tokens (CamelCase, snake_case, dotted, or path-like)
_SYMBOL_RE = re.compile(
    r"\b(?:"
    r"[a-z_][a-z0-9_]*\.[a-z_.][\w.]*"       # dotted.path
    r"|[A-Z][a-z0-9]+(?:[A-Z][a-zA-Z0-9]*)+"  # CamelCase (two humps minimum)
    r"|[a-z_]+_[a-z_]+"                       # snake_case
    r"|[\w-]+/[\w./-]+"                       # path/like
    r")\b"
)


@dataclass
class TaskProfile:
    task_type: str            # 'factual' | 'structural' | 'multi_hop'
    complexity: float         # 0..1
    knowledge_dependence: float
    dependency_depth: int     # graph expansion hops for retrieval
    context_budget_tokens: int
    retrieval_top_k: int
    mentioned_symbols: list[str]

    def as_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "complexity": round(self.complexity, 2),
            "knowledge_dependence": round(self.knowledge_dependence, 2),
            "dependency_depth": self.dependency_depth,
            "context_budget_tokens": self.context_budget_tokens,
            "retrieval_top_k": self.retrieval_top_k,
            "mentioned_symbols": self.mentioned_symbols,
        }


def profile_task(query: str) -> TaskProfile:
    words = query.split()
    symbols = _SYMBOL_RE.findall(query)

    multi_hop = bool(_MULTI_HOP_MARKERS.search(query))
    structural = bool(_STRUCTURAL_MARKERS.search(query))
    factual = bool(_FACTUAL_MARKERS.search(query))

    if multi_hop:
        task_type = "multi_hop"
    elif structural:
        task_type = "structural"
    elif factual:
        task_type = "factual"
    else:
        task_type = "structural"  # default middle ground

    # Complexity: length + multi-hop markers + number of distinct symbols
    complexity = min(
        1.0,
        0.15
        + 0.02 * len(words)
        + (0.35 if multi_hop else 0.0)
        + 0.08 * min(len(set(symbols)), 4),
    )
    knowledge_dependence = min(1.0, 0.5 + 0.1 * min(len(set(symbols)), 4)
                               + (0.2 if task_type != "factual" else 0.0))

    if task_type == "factual":
        budget, top_k, depth = 800, 6, 0
    elif task_type == "structural":
        budget, top_k, depth = 1600, 10, 1
    else:  # multi_hop
        budget, top_k, depth = 2800, 14, 2

    # Scale budget mildly with complexity
    budget = int(budget * (0.75 + 0.5 * complexity))

    return TaskProfile(
        task_type=task_type,
        complexity=complexity,
        knowledge_dependence=knowledge_dependence,
        dependency_depth=depth,
        context_budget_tokens=budget,
        retrieval_top_k=top_k,
        mentioned_symbols=sorted(set(symbols))[:10],
    )
