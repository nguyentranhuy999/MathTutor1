from src.models import DiagnosisLabel
from src.pipeline import run_tutoring_pipeline


def test_pipeline_runs_end_to_end_for_intermediate_target_case():
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )

    result = run_tutoring_pipeline(problem_text, "12 - 10 = 2\nAnswer is 2.", use_llm=False)

    assert result.reference.final_answer == 476.0
    assert result.diagnosis.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING
    assert result.hint_result.verification_passed is True
    assert result.hint_plan.teacher_move.value == "refocus_target"
