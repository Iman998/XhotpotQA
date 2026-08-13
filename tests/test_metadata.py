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


def test_citations_identify_public_data_but_not_an_unpublished_article() -> None:
    for relative_path in ("README.md", "dataset_card/README.md"):
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert "@misc{barati2026xhotpotqa" in text
        assert "journal = {Language Resources and Evaluation}" not in text
        assert "https://arxiv.org/" not in text
        assert "https://huggingface.co/datasets/Iman998/XHotpotQA" in text
        assert "52b8bee41ff2bb0d41cd400ff5646c0e800b5127" in text
        assert "manuscript in preparation" in text
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
    assert "Iman998/XHotpotQA" in card
    assert "revision=DATA_REVISION" in card
    assert 'revision="52b8bee41ff2bb0d41cd400ff5646c0e800b5127"' in card


def test_repository_docs_and_builder_distinguish_the_two_release_tracks() -> None:
    audited_config = "xhotpotqa_v1_audited"
    data_revision = "52b8bee41ff2bb0d41cd400ff5646c0e800b5127"
    for relative_path in (
        "README.md",
        "data/README.md",
        "docs/SCHEMA.md",
        "docs/XHOTPOTQA_PLUS.md",
    ):
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert audited_config in text
        assert data_revision in text

    data_readme = (REPOSITORY / "data/README.md").read_text(encoding="utf-8")
    assert "prospective corrected canonical release" in data_readme
    assert "publishes the canonical files" not in data_readme

    plus_docs = (REPOSITORY / "docs/XHOTPOTQA_PLUS.md").read_text(encoding="utf-8")
    assert "prospective paired-view form" in plus_docs
    assert "It is published as" not in plus_docs

    changelog = (REPOSITORY / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Publish the audit-preserving `xhotpotqa_v1_audited`" in changelog
    assert "Publish XHotpotQA+ as a second Hugging Face configuration" not in changelog
    assert "the incomplete parallel artifacts are not published" in changelog

    builder = (REPOSITORY / "scripts/build_hf_public_v1.py").read_text(encoding="utf-8")
    assert f'CONFIG_NAME = "{audited_config}"' in builder


def test_citation_cff_tracks_public_code_but_omits_unminted_release_identifiers() -> None:
    payload = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text(encoding="utf-8"))

    assert payload["type"] == "software"
    assert payload["version"] == "0.3.0"
    assert payload["repository-code"] == "https://github.com/Iman998/XhotpotQA"
    assert "24-Language" not in payload["title"]
    assert "date-released" not in payload
    assert "url" not in payload
