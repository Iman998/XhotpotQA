from pathlib import Path

import yaml

REPOSITORY = Path(__file__).resolve().parents[1]


def test_pending_manuscript_citations_make_no_publication_claim() -> None:
    for relative_path in ("README.md", "dataset_card/README.md"):
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert "@unpublished{barati2026xhotpotqa" in text
        assert "journal = {Language Resources and Evaluation}" not in text
        assert "https://arxiv.org/" not in text
        assert "pending deposit" in text
        assert "A 24-Language Benchmark" not in text


def test_citation_cff_tracks_public_code_but_omits_unminted_release_identifiers() -> None:
    payload = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text(encoding="utf-8"))

    assert payload["type"] == "software"
    assert payload["version"] == "0.3.0"
    assert payload["repository-code"] == "https://github.com/Iman998/XhotpotQA"
    assert "24-Language" not in payload["title"]
    assert "date-released" not in payload
    assert "url" not in payload
