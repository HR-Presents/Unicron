import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "backend/app/investigation.py"


def source_expression():
    tree = ast.parse(SOURCE.read_text())

    workflow = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_execute_workflow"
    )

    context = next(
        node.value for node in ast.walk(workflow)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "context"
            for target in node.targets
        )
        and isinstance(node.value, ast.Dict)
    )

    for key, value in zip(context.keys, context.values):
        if isinstance(key, ast.Constant) and key.value == "source_excerpts":
            return compile(
                ast.Expression(body=value),
                str(SOURCE),
                "eval",
            )

    raise AssertionError("Source excerpts expression missing")


def passage(status, source_type="policy"):
    return {
        "citation": "document#p1",
        "text": "Healthcare policy evidence.",
        "verification_status": status,
        "authority": "Test Authority",
        "jurisdiction": "UAE",
        "official_url": "https://example.org/policy",
        "source_type": source_type,
    }


def test_unverified_evidence_excluded():
    passages = [passage("unverified")]
    result = eval(source_expression(), {"passages": passages})
    assert result == []


def test_verified_evidence_included():
    passages = [passage("verified")]
    result = eval(source_expression(), {"passages": passages})
    assert result == [{
        "citation": "document#p1",
        "text": "Healthcare policy evidence.",
    }]


def test_rejected_evidence_excluded():
    passages = [passage("rejected")]
    result = eval(source_expression(), {"passages": passages})
    assert result == []


def test_unverified_evidence_cannot_displace_verified():
    passages = [
        passage("unverified"),
        passage("verified"),
    ]
    result = eval(source_expression(), {"passages": passages})
    assert len(result) == 1
    assert result[0]["text"] == "Healthcare policy evidence."
