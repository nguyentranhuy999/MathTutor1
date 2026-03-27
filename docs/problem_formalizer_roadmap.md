# Roadmap

## Goal

Build the tutoring system around a structured execution-first core:

`Problem -> Problem Formalizer -> Executable Solver -> Evidence Builder -> Diagnosis -> Pedagogy Planner -> Hint`

## Principles

- representation before policy
- structured artifacts are the main source of truth
- prose is a rendered view, not the canonical state
- no return to the legacy pipeline

## Completed

- shared core schemas
- formalizer/runtime/pedagogy schemas
- deterministic `problem formalizer`
- deterministic `student work formalizer`
- shared trace builder
- executable solver
  - `ExecutablePlan` compilation
  - deterministic execution
  - `CanonicalReference` building
- deterministic `evidence builder`
  - alignment of problem, reference, and student artifacts
  - first-divergence localization
  - mechanism-oriented evidence extraction
- deterministic `diagnosis`
  - evidence-first label mapping
  - localization and subtype assignment
- deterministic `pedagogy planner`
  - teacher-move selection
  - hint-level and disclosure-budget planning
  - focus-point and spoiler-budget planning
- deterministic `hint`
  - short pedagogically aligned hint generation
  - spoiler and alignment verification
- end-to-end `pipeline runner`
  - single entry point that executes the full tutoring loop

## Current State

The deterministic pipeline is now complete:

`Problem -> Problem Formalizer -> Executable Solver -> Student Work Formalizer -> Evidence Builder -> Diagnosis -> Pedagogy Planner -> Hint -> Verified Hint Result`

## Future Extensions

1. LLM-backed formalization fallback
2. LLM-backed student-work parsing fallback
3. richer hint surface generation with the same verifier layer
4. multi-candidate plan generation and reranking

## Long-Term Completion Criteria

- references are built from executable artifacts, not prose parsing
- diagnosis is grounded mainly in structured evidence
- hints are controlled by explicit pedagogy plans
- all core modules depend on stable shared schemas
