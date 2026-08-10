from xhotpotqa.data.assignment import LanguageAssigner


def test_assignment_is_stable_and_unit_specific() -> None:
    assigner = LanguageAssigner(seed=42)
    first = assigner.assign("source-1", "question-answer")
    assert first == assigner.assign("source-1", "question-answer")
    assignments = {assigner.assign("source-1", f"paragraph:{index}") for index in range(30)}
    assert len(assignments) > 1
