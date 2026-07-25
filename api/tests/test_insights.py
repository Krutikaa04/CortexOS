from cortex.kernel.insights import (
    detect_cycles,
    detect_dead_code,
    repository_insights,
    trace_flow,
)


def test_detect_cycles_finds_loop_ignores_dag():
    cycles = detect_cycles([("a", "b"), ("b", "c"), ("c", "a"), ("x", "y")])
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a", "b", "c"}


def test_detect_cycles_direct_two_node():
    cycles = detect_cycles([("a", "b"), ("b", "a")])
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a", "b"}


NODES = [
    {"id": "1", "qualified_name": "m.py::used", "kind": "function", "path": "m.py", "tokens": 10},
    {"id": "2", "qualified_name": "m.py::orphan", "kind": "function", "path": "m.py", "tokens": 5},
    {"id": "3", "qualified_name": "m.py::main", "kind": "function", "path": "m.py", "tokens": 5},
    {"id": "4", "qualified_name": "svc.py::Base", "kind": "class", "path": "svc.py", "tokens": 20},
    {"id": "5", "qualified_name": "m.py::__init__", "kind": "method", "path": "m.py", "tokens": 3},
]
EDGES = [
    {"from_id": "3", "to_id": "1", "kind": "calls"},
    {"from_id": "1", "to_id": "4", "kind": "inherits"},
]


def test_dead_code_reports_only_unreferenced_non_entrypoints():
    dead = {d["symbol"] for d in detect_dead_code(NODES, EDGES)}
    assert "orphan" in dead          # no inbound, not entrypoint
    assert "used" not in dead        # referenced by main
    assert "main" not in dead        # entrypoint name
    assert "Base" not in dead        # inherited from
    assert "__init__" not in dead    # dunder entrypoint


def test_dead_code_has_evidence():
    items = detect_dead_code(NODES, EDGES)
    assert all(i["evidence"] for i in items)


def test_repository_insights_hotspots_and_layers():
    ins = repository_insights(NODES, EDGES)
    # 'used' and 'Base' each referenced once -> hotspots
    hot = {h["symbol"] for h in ins["hotspots"]}
    assert "used" in hot and "Base" in hot
    assert ins["totals"]["artifacts"] == 5
    assert any(layer["files"] > 0 for layer in ins["layers"])


def test_trace_flow_forward_reach():
    levels = trace_flow(EDGES, ["3"])
    # main -> used (depth 1); inherits is not a flow edge, so it stops
    assert levels[0]["depth"] == 1
    assert levels[0]["nodes"][0]["id"] == "1"
