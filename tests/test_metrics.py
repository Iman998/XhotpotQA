from xhotpotqa.evaluation.metrics import score_example


def test_joint_metric_uses_joint_precision_and_recall() -> None:
    score = score_example(
        "the blue whale",
        "blue whale",
        "en",
        [("p0", 0)],
        [("p0", 0), ("p1", 1)],
    )
    assert score.answer.exact_match == 1.0
    assert score.support.precision == 1.0
    assert score.support.recall == 0.5
    assert score.joint.precision == 1.0
    assert score.joint.recall == 0.5
    assert score.joint.f1 == 2 / 3


def test_cjk_uses_character_tokens() -> None:
    score = score_example("北京大学", "北京", "zh", [], [])
    assert score.answer.precision == 0.5
    assert score.answer.recall == 1.0
