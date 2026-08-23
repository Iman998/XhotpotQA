import re
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
        assert "https://huggingface.co/datasets/Iman998/XhotpotQA" in text
        assert "52b8bee41ff2bb0d41cd400ff5646c0e800b5127" in text
        assert "manuscript in preparation" in text
        assert "A 24-Language Benchmark" not in text


def test_public_dataset_card_defaults_to_v1_1_and_retains_legacy_v1() -> None:
    metadata = _dataset_card_metadata()

    assert metadata["pretty_name"] == "XHotpotQA"
    assert metadata["license"] == "cc-by-sa-4.0"
    assert set(metadata["language"]) == set(LANGUAGE_CODES)
    assert len(metadata["language"]) == len(LANGUAGE_CODES)
    assert metadata["size_categories"] == ["10K<n<100K"]
    assert metadata["configs"] == [
        {
            "config_name": "xhotpotqa_v1_1_audited",
            "default": True,
            "data_files": [
                {
                    "split": "train",
                    "path": "data/xhotpotqa_v1_1_audited/train-*.parquet",
                },
                {
                    "split": "validation",
                    "path": "data/xhotpotqa_v1_1_audited/validation-*.parquet",
                },
            ],
        },
        {
            "config_name": "xhotpotqa_v1_audited",
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
        },
    ]

    card = (REPOSITORY / "dataset_card/README.md").read_text(encoding="utf-8")
    assert "Iman998/XhotpotQA" in card
    assert "revision=DATA_REVISION" in card
    assert "1d29e7918cf1acc045726c70fddba82371833090" in card
    assert "source_sentences" in card
    assert "52b8bee41ff2bb0d41cd400ff5646c0e800b5127" in card


def test_all_hub_cards_pin_exact_snapshots_and_canonical_slugs() -> None:
    collection_url = (
        "https://huggingface.co/collections/Iman998/"
        "xhotpotqa-cross-lingual-multi-hop-qa-6a888df6aee4a4f5612c3a1a"
    )
    cards = {
        "dataset_card/README.md": (
            "Iman998/XhotpotQA",
            "1d29e7918cf1acc045726c70fddba82371833090",
            "xhotpotqa_v1_1_audited",
        ),
        "dataset_cards/v2/README.md": (
            "Iman998/XhotpotQA-V2",
            "b05ba394ad7312e85625624c90d10258cbab31af",
            "xhotpotqa_v2_audited_rc1",
        ),
        "dataset_cards/judge_v1/README.md": (
            "Iman998/XhotpotQA-GLM52-Judge-V1",
            "ba891ae62ed989606c9fc2fd5f08f9e88ef37547",
            "xhotpotqa_glm52_judge_v1",
        ),
        "dataset_cards/judge_v2/README.md": (
            "Iman998/XhotpotQA-GLM52-Judge-V2",
            "0f9cd568fabd7f7ad3b3d9a72e31ae8aeb936840",
            "xhotpotqa_glm52_judge_v2",
        ),
    }

    for relative_path, (repo_id, revision, config_name) in cards.items():
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        lines = text.splitlines()
        closing = lines.index("---", 1)
        metadata = yaml.safe_load("\n".join(lines[1:closing]))

        assert repo_id in text
        assert revision in text
        assert config_name in {config["config_name"] for config in metadata["configs"]}
        assert collection_url in text
        assert "huggingface.co/datasets/Iman998/XHotpotQA" not in text
        assert not re.search(r"__(?:[A-Z0-9_]+REVISION[A-Z0-9_]*)__", text)


def test_release_cards_keep_counts_and_model_claims_in_scope() -> None:
    v2 = (REPOSITORY / "dataset_cards/v2/README.md").read_text(encoding="utf-8")
    judge_v1 = (REPOSITORY / "dataset_cards/judge_v1/README.md").read_text(encoding="utf-8")
    judge_v2 = (REPOSITORY / "dataset_cards/judge_v2/README.md").read_text(encoding="utf-8")

    assert all(value in v2 for value in ("22,836", "23,066", "15,433", "7,403"))
    assert "Gemma 4 31B Instruct" in v2
    assert "not the corrected canonical V2" in v2

    for card in (judge_v1, judge_v2):
        assert "2,760" in card
        assert "requested" in card.lower()
        assert "glm-5.2" in card.lower()
        assert "provider-resolved" in card.lower()
        assert "not paired" in card.lower() or "unpaired" in card.lower()

    assert "Gemma 4 31B-generated" in judge_v2


def test_release_cards_share_a_responsive_hub_safe_visual_contract() -> None:
    cards = {
        "dataset_cards/v2/README.md": "## Record structure",
        "dataset_cards/judge_v1/README.md": "## Public schema",
        "dataset_cards/judge_v2/README.md": "## Public schema",
    }

    for relative_path, schema_heading in cards.items():
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

        assert "background:linear-gradient(" in text
        assert "flex-wrap:wrap" in text
        assert "border-radius:999px" in text
        assert "font-size:24px" in text
        assert "border-left:5px" in text
        assert "## Dataset at a glance" in text
        assert "## Quickstart" in text
        assert schema_heading in text
        assert "### Shape-only" in text
        assert "## Methodology and " in text
        assert "## Limitations" in text
        assert "## Citation" in text
        assert "## Release family" in text
        assert "img.shields.io" not in text
        assert text.count("```") % 2 == 0
        assert "\ufffd" not in text

        without_display_math = re.sub(r"\$\$.*?\$\$", "", prose, flags=re.DOTALL)
        assert not re.search(r"(?<!\$)\$(?!\$)", without_display_math)
        assert prose.count(r"\\(") == prose.count(r"\\)")

        headings = {
            re.sub(r"[^a-z0-9 -]", "", re.sub(r"^#{1,6}\s+", "", line).lower())
            .strip()
            .replace(" ", "-")
            for line in text.splitlines()
            if re.match(r"^#{1,6}\s+", line)
        }
        targets = set(re.findall(r'href="#([a-z0-9-]+)"', text))
        assert targets <= headings


def test_dataset_card_navigation_targets_plain_stable_headings() -> None:
    card = (REPOSITORY / "dataset_card/README.md").read_text(encoding="utf-8")
    heading_text = [
        re.sub(r"^#{1,6}\s+", "", line).strip()
        for line in card.splitlines()
        if re.match(r"^#{1,6}\s+", line)
    ]
    headings = {
        re.sub(r"[ _]+", "-", heading.lower())
        for heading in heading_text
        if re.fullmatch(r"[A-Za-z0-9 _-]+", heading)
    }
    markdown_targets = set(re.findall(r"\]\(#([a-z0-9-]+)\)", card))
    html_targets = set(re.findall(r'href="#([a-z0-9-]+)"', card))
    targets = markdown_targets | html_targets

    assert targets <= headings


def test_dataset_card_uses_hugging_face_katex_delimiters() -> None:
    """Guard the Hub-specific math contract documented for repository cards."""
    card = (REPOSITORY / "dataset_card/README.md").read_text(encoding="utf-8")
    prose = re.sub(r"```.*?```", "", card, flags=re.DOTALL)

    assert not re.search(r"(?m)^\s*\\[\[\]]\s*$", prose)
    assert not re.search(r"(?<!\\)\\[()]", prose)
    assert prose.count("$$") == 8
    without_display_math = re.sub(r"\$\$.*?\$\$", "", prose, flags=re.DOTALL)
    assert not re.search(r"(?<!\$)\$(?!\$)", without_display_math)
    assert prose.count(r"\\(") > 0
    assert prose.count(r"\\(") == prose.count(r"\\)")
    assert r"\\(L_q\\)" in prose


def test_repository_docs_and_builder_distinguish_the_two_release_tracks() -> None:
    audited_config = "xhotpotqa_v1_audited"
    source_complete_config = "xhotpotqa_v1_1_audited"
    data_revision = "52b8bee41ff2bb0d41cd400ff5646c0e800b5127"
    source_complete_revision = "1d29e7918cf1acc045726c70fddba82371833090"
    for relative_path in (
        "README.md",
        "data/README.md",
        "docs/SCHEMA.md",
        "docs/XHOTPOTQA_PLUS.md",
    ):
        text = (REPOSITORY / relative_path).read_text(encoding="utf-8")
        assert audited_config in text
        assert data_revision in text
        assert source_complete_config in text
        assert source_complete_revision in text

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
    assert f'CONFIG_NAME = "{source_complete_config}"' in builder
    assert 'BUILD_VERSION = "xhotpotqa-public-v1-builder/1.2.0"' in builder
    assert '"release_version": "xhotpotqa-public-v1.1-audited"' in builder


def test_citation_cff_tracks_public_code_but_omits_unminted_release_identifiers() -> None:
    payload = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text(encoding="utf-8"))

    assert payload["type"] == "software"
    assert payload["version"] == "0.4.1"
    assert payload["repository-code"] == "https://github.com/Iman998/XhotpotQA"
    assert "24-Language" not in payload["title"]
    assert str(payload["date-released"]) == "2026-08-23"
    assert "url" not in payload
    assert [author["family-names"] for author in payload["authors"]] == [
        "Barati",
        "Ghafouri",
        "Minaei-Bidgoli",
    ]


def test_package_and_citation_versions_match_the_release() -> None:
    pyproject = (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
    package_init = (REPOSITORY / "src/xhotpotqa/__init__.py").read_text(
        encoding="utf-8"
    )
    citation = yaml.safe_load((REPOSITORY / "CITATION.cff").read_text(encoding="utf-8"))

    assert 'version = "0.4.1"' in pyproject
    assert '__version__ = "0.4.1"' in package_init
    assert citation["version"] == "0.4.1"
    assert str(citation["date-released"]) == "2026-08-23"


def test_public_authorship_matches_the_final_three_author_manuscript() -> None:
    public_metadata = [
        REPOSITORY / "CITATION.cff",
        REPOSITORY / "README.md",
        REPOSITORY / "dataset_card/README.md",
    ]
    for path in public_metadata:
        text = path.read_text(encoding="utf-8").casefold()
        assert "iman" in text and "barati" in text, path
        assert "arash" in text and "ghafouri" in text, path
        assert "behrouz" in text and "minaei-bidgoli" in text, path
