"""Token estimation.

Real token counts for model calls come from the model runtime itself
(prompt_eval_count / eval_count) and are always preferred in metrics.
This estimator exists for planning decisions made *before* a model call:
context budgets, chunk sizing, packing. Both the baseline and the CortexOS
pipeline use this same estimator, so comparisons stay fair even though the
estimate is approximate.
"""


def estimate_tokens(text: str) -> int:
    """~4 characters per token — the standard rough heuristic for English
    and code. Deliberately simple and dependency-free."""
    if not text:
        return 0
    return max(1, len(text) // 4)
