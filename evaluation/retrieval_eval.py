"""Offline, labeled evaluation for UNICRON lexical evidence retrieval.

Synthetic fixtures measure retrieval behavior, not real-world policy accuracy.
Run: .venv/bin/python evaluation/retrieval_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.retrieval_rank import rank_passages


PASSAGES = [
    {
        "document_id": "uae_notice",
        "position": 1,
        "filename": "uae_notice.txt",
        "content": (
            "Municipal authorities shall issue timely public notices "
            "during water supply interruptions, including expected "
            "restoration times and alternative service arrangements."
        ),
        "jurisdiction": "UAE",
    },
    {
        "document_id": "sg_notice",
        "position": 1,
        "filename": "sg_notice.txt",
        "content": (
            "Public utilities provide residents with timely notifications "
            "during water supply disruptions and publish restoration "
            "estimates and emergency alternative arrangements."
        ),
        "jurisdiction": "Singapore",
    },
    {
        "document_id": "eu_privacy",
        "position": 1,
        "filename": "eu_privacy.txt",
        "content": (
            "Personal data controllers must implement appropriate "
            "security measures and document processing safeguards "
            "to protect individuals from unauthorized disclosure."
        ),
        "jurisdiction": "EU",
    },
    {
        "document_id": "clinical_samples",
        "position": 1,
        "filename": "clinical_samples.txt",
        "content": (
            "Hospitals maintain clinical laboratory sample records "
            "including specimen identification, storage temperatures "
            "and laboratory quality assurance procedures."
        ),
        "jurisdiction": "Singapore",
    },
    {
        "document_id": "water_irrelevant",
        "position": 1,
        "filename": "water_irrelevant.txt",
        "content": (
            "Water quality laboratories conduct chemical testing "
            "of samples and monitor mineral concentrations "
            "through calibrated analytical instruments."
        ),
        "jurisdiction": "UAE",
    },
]

QUERIES = [
    {
        "id": "water_notice",
        "query": "water supply restoration notices",
        "relevant": {"uae_notice#p1", "sg_notice#p1"},
        "jurisdictions": {"UAE", "Singapore"},
    },
    {
        "id": "data_security",
        "query": "personal data security processing",
        "relevant": {"eu_privacy#p1"},
        "jurisdictions": {"EU"},
    },
    {
        "id": "clinical_storage",
        "query": "clinical laboratory storage",
        "relevant": {"clinical_samples#p1"},
        "jurisdictions": {"Singapore"},
    },
]


def evaluate():
    results = []

    for item in QUERIES:
        tokens = item["query"].casefold().split()
        ranked = rank_passages(PASSAGES, tokens)[:5]

        citations = [row["citation"] for row in ranked]
        relevant_found = set(citations) & item["relevant"]

        precision = (
            len(relevant_found) / len(citations)
            if citations else 0.0
        )
        recall = len(relevant_found) / len(item["relevant"])

        source_lookup = {
            f"{p['document_id']}#p{p['position']}": p
            for p in PASSAGES
        }
        citation_accuracy = (
            sum(
                1 for row in ranked
                if row["citation"] in source_lookup
                and row["content"] ==
                source_lookup[row["citation"]]["content"]
            ) / len(ranked)
            if ranked else 0.0
        )

        found_jurisdictions = {
            row["jurisdiction"]
            for row in ranked
            if row["citation"] in item["relevant"]
        }
        jurisdiction_coverage = (
            len(found_jurisdictions & item["jurisdictions"])
            / len(item["jurisdictions"])
        )

        duplicate_rate = (
            1 - len(set(citations)) / len(citations)
            if citations else 0.0
        )

        results.append({
            "query_id": item["id"],
            "precision_at_5": round(precision, 3),
            "recall_at_5": round(recall, 3),
            "citation_accuracy": round(citation_accuracy, 3),
            "jurisdiction_coverage": round(jurisdiction_coverage, 3),
            "duplicate_rate": round(duplicate_rate, 3),
            "returned_citations": citations,
        })

    metrics = [
        "precision_at_5",
        "recall_at_5",
        "citation_accuracy",
        "jurisdiction_coverage",
        "duplicate_rate",
    ]

    summary = {
        metric: round(
            sum(row[metric] for row in results) / len(results), 3
        )
        for metric in metrics
    }

    return {
        "evaluation_type": "synthetic_offline_lexical_retrieval",
        "query_count": len(QUERIES),
        "passage_count": len(PASSAGES),
        "summary": summary,
        "queries": results,
        "limitations": (
            "Small synthetic fixture; not evidence of real-world "
            "retrieval accuracy or policy correctness."
        ),
    }


if __name__ == "__main__":
    report = evaluate()
    output = ROOT / "evaluation" / "retrieval_results.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"\nSaved: {output}")
