import uuid

from cortex import answer_cache as ac
from cortex.config import get_settings

V = uuid.uuid4()
G = {"status": "ready", "nodes": 10, "edges": 20}


def test_key_ignores_case_whitespace_punctuation():
    assert ac.make_key(V, "What does  Signer do?", G) == ac.make_key(V, " what does signer do ", G)


def test_gap_answers_are_not_cacheable():
    assert ac._ADMITS_GAP.search("The information provided does not contain details on X.")
    assert not ac._ADMITS_GAP.search("The cart total is computed in Cart.total() by summing items.")


def test_key_changes_with_version_graph_and_config(monkeypatch):
    base = ac.make_key(V, "q", G)
    assert ac.make_key(uuid.uuid4(), "q", G) != base           # other repo/version
    assert ac.make_key(V, "q", {**G, "edges": 21}) != base      # graph rebuilt differently
    assert ac.make_key(V, "other", G) != base
    monkeypatch.setenv("CORTEX_GRAPH_MAX_HOPS", "3")
    get_settings.cache_clear()
    try:
        assert ac.make_key(V, "q", G) != base                    # retrieval config
    finally:
        monkeypatch.delenv("CORTEX_GRAPH_MAX_HOPS")
        get_settings.cache_clear()
