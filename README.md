# Problem Formalizer

This repository is the clean foundation for the new math tutoring architecture:

`Problem -> Problem Formalizer -> Executable Solver -> Evidence Builder -> Diagnosis -> Pedagogy Planner -> Hint`

Completed so far:

- shared core schemas
- formalizer/runtime/pedagogy schemas
- deterministic problem formalizer
- deterministic student-work formalizer
- shared reference trace builder
- executable runtime with plan compilation, execution, and canonical reference building
- deterministic evidence builder
- deterministic diagnosis engine
- deterministic pedagogy planner
- deterministic hint generation and verification
- end-to-end tutoring pipeline runner
- tests for `models`, `formalizer`, `runtime`, `evidence`, `diagnosis`, `pedagogy`, `hint`, and `pipeline`

## Current Structure

- `src/models`
  - shared types and structured artifacts
- `src/formalizer`
  - problem formalization, student-work formalization, and trace extraction
- `src/runtime`
  - executable plan compilation and execution
- `src/evidence`
  - structured evidence building from problem, reference, and student artifacts
- `src/diagnosis`
  - evidence-first diagnosis engine
- `src/pedagogy`
  - deterministic pedagogy planner
- `src/hint`
  - hint generation and verification
- `src/pipeline`
  - end-to-end tutoring pipeline runner
- `docs/problem_formalizer_roadmap.md`
  - architecture roadmap

## Testing

```powershell
.\venv\Scripts\python.exe -m pytest tests\formalizer tests\models tests\runtime tests\evidence tests\diagnosis tests\pedagogy tests\hint tests\pipeline
```

## Current Scope

The repository now supports an end-to-end deterministic tutoring pipeline:

- problem formalization
- executable reference solving
- student-work formalization
- evidence building
- diagnosis
- pedagogy planning
- hint generation and verification

Future extensions can add LLM-backed fallbacks or richer natural-language hints,
but the core tutoring loop is now complete without depending on a legacy pipeline.
