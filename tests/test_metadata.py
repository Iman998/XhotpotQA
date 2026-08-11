from pathlib import Path

import yaml

from xhotpotqa.languages import LANGUAGE_CODES

REPOSITORY = Path(__file__).resolve().parents[1]


def _dataset_card_metadata() -> dict[str, object]:
    lines = (REPOSITORY / "dataset_card/README.md").read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---"
    closing = lines.index("---", 1)
    metadata = yaml.safe_load("\n".join(lines[1:closing]))
    assert isinstance(metadata, dict)
    return metadata


def test_pending_manuscript_citations_make_no_publication_claim() -> None:
    for relative_path in ("README.md", "dataset_card/README.md"):
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert "@unpublished{barati2026xhotpotqa" in text
        assert "journal = {Language Resources and Evaluation}" not in text
        assert "https://arxiv.org/" not in text
        assert "Manuscript and resource release in preparation" in text
        assert "A 24-Language Benchmark" not in text


def test_public_dataset_card_declares_only_the_audited_parquet_config() -> None:
    metadata = _dataset_card_metadata()

    assert metadata["pretty_name"] == "XHotpotQA"
    assert metadata["license"] == "cc-by-sa-4.0"
    assert set(metadata["language"]) == set(LANGUAGE_CODES)
    assert len(metadata["language"]) == len(LANGUAGE_CODES)
    assert metadata["size_categories"] == ["10K<n<100K"]
    assert metadata["configs"] == [
        {
            "config_name": "xhotpotqa_v1_audited",
            "default": True,
            "data_files": [
                {
                    "split": "train",
                    "path": "data/xhotpotqa_v1_audited/train-*.parquet",
                },
                {
                    "split": "validation",
                    "path": "data/xhotpotqa_v1_audited/validation-*.parquet",
                },
            ],
        }
    ]

    card = (REPOSITORY / "dataset_card/README.md").read_text(encoding="utf-8")
    assert "iman998/XhotpotQA" in card
    assert "iman998/XHotpotQA" not in card


def test_citation_cff_tracks_public_code_but_omits_unminted_release_identifiers() -> None:
    payload = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text(encoding="utf-8"))

    assert payload["type"] == "software"
    assert payload["version"] == "0.3.0"
    assert payload["repository-code"] == "https://github.com/Iman998/XhotpotQA"
    assert "24-Language" not in payload["title"]
    assert "date-released" not in payload
    assert "url" not in payload
