"""Information Requirement Generator.

Before retrieving anything, ask: what must be KNOWN to answer this?
Semantically similar information != information actually necessary.

MVP strategy: ask the local task model to decompose the query into
requirements (strict JSON). If the model output is unusable, fall back to
deterministic keyword-based requirements so the pipeline never dies here.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from cortex.kernel.profiler import TaskProfile
from cortex.models_client import ModelUnavailableError, get_model_client

log = logging.getLogger("cortex.kernel.requirements")

_PROMPT = """\
Decompose this question about a software repository into the minimal set of
information requirements needed to answer it. A requirement is one specific
piece of knowledge that must be found in the codebase or docs.

Question: {query}

Respond with ONLY a JSON array (2 to {max_reqs} items), each item:
{{"id": "r1", "description": "...", "keywords": ["...", "..."]}}

JSON:"""

_STOPWORDS = frozenset(
    "the a an is are was were do does did what which where who when how why "
    "will would can could should of in on at to for with and or if i we you "
    "it this that these those be been being have has had".split()
)


@dataclass
class Requirement:
    id: str
    description: str
    keywords: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"id": self.id, "description": self.description, "keywords": self.keywords}


async def generate_requirements(
    query: str, profile: TaskProfile, *, allow_model: bool = True
) -> tuple[list[Requirement], str]:
    """Returns (requirements, strategy) where strategy is 'model' or 'heuristic'.

    allow_model=False is the fast path: skip the requirement-decomposition
    LLM call entirely (measured at 11-43s on local CPU) and use the
    deterministic heuristic. Internal structured calls use the configurable
    internal model role, which defaults to the task model.
    """
    from cortex.config import get_settings

    max_reqs = {"factual": 3, "structural": 4, "multi_hop": 6}[profile.task_type]
    if not allow_model:
        return _heuristic_requirements(query, profile, max_reqs), "heuristic"
    try:
        result = await get_model_client().generate(
            _PROMPT.format(query=query, max_reqs=max_reqs),
            model=get_settings().internal_model or None,
            temperature=0.0,
            max_tokens=512,
        )
        requirements = _parse_model_output(result["text"], max_reqs)
        if requirements:
            return requirements, "model"
        log.warning("model requirement output unusable, falling back to heuristic")
    except ModelUnavailableError:
        log.warning("model unavailable for requirements, falling back to heuristic")

    return _heuristic_requirements(query, profile, max_reqs), "heuristic"


def _parse_model_output(text: str, max_reqs: int) -> list[Requirement]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    requirements = []
    for i, item in enumerate(items[:max_reqs]):
        if not isinstance(item, dict) or not item.get("description"):
            continue
        keywords = [str(k) for k in item.get("keywords", []) if isinstance(k, (str, int))]
        requirements.append(
            Requirement(
                id=str(item.get("id") or f"r{i + 1}"),
                description=str(item["description"]),
                keywords=keywords[:6],
            )
        )
    return requirements


def _heuristic_requirements(query: str, profile: TaskProfile, max_reqs: int) -> list[Requirement]:
    """Fallback: mentioned symbols become requirements; remaining content
    words become one general requirement."""
    requirements: list[Requirement] = []
    for i, symbol in enumerate(profile.mentioned_symbols[: max_reqs - 1]):
        requirements.append(
            Requirement(
                id=f"r{i + 1}",
                description=f"Definition and behavior of {symbol}",
                keywords=[symbol],
            )
        )
    content_words = [
        w.strip("?.,!\"'()") for w in query.lower().split()
        if w.strip("?.,!\"'()") not in _STOPWORDS and len(w) > 2
    ]
    requirements.append(
        Requirement(
            id=f"r{len(requirements) + 1}",
            description=query,
            keywords=content_words[:6],
        )
    )
    return requirements
