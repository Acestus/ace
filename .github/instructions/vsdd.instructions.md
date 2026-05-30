````instructions
# Verified Spec-Driven Development (VSDD) Instructions

## Purpose
Use VSDD for features where correctness, security, and long-term maintainability matter.

VSDD = Spec-Driven Development + Test-Driven Development + Adversarial Verification.

## Core Rules
1. **Spec first**: No implementation before a written spec is approved.
2. **Tests first**: Follow strict Red → Green → Refactor.
3. **Adversarial review**: Critique must be concrete, actionable, and severity-tagged.
4. **Traceability**: Every implementation change maps back to spec and tests.
5. **Convergence gate**: Do not declare done until spec, tests, implementation, and verification all pass.

## Required VSDD Phases

### Phase 1 — Spec Crystallization
Produce and review:
- Behavioral contract (preconditions, postconditions, invariants)
- Interface contract (input/output/error types)
- Edge-case catalog
- Non-functional requirements
- Verification architecture:
  - Provable properties
  - Pure core vs effectful shell boundary
  - Tool selection for proofs/model checking

No implementation code in this phase.

### Phase 2 — Test-First Implementation
- Generate tests directly from spec.
- Ensure tests fail first (Red gate).
- Implement minimum code to make tests pass.
- Refactor only with all tests green.

### Phase 3 — Adversarial Refinement
Review for:
- Spec fidelity gaps
- Weak/tautological tests
- Hidden coupling/race conditions/leaks
- Security and validation gaps
- Behavior implemented but not specified

All findings must include: severity, location, defect, fix.

### Phase 4 — Feedback Integration Loop
Route findings to the right loop:
- Spec flaws → back to Phase 1
- Test flaws → back to Phase 2 test generation
- Implementation flaws → refactor/rework in Phase 2
- New edge cases → add to spec and tests

### Phase 5 — Formal Hardening
Where applicable:
- Execute proof harnesses/contracts
- Run fuzz testing and static/security checks
- Run mutation testing to verify test quality
- Audit purity boundary integrity

### Phase 6 — Convergence
Done means all are true:
- Spec has no material ambiguities/gaps
- Tests cover meaningful scenarios and mutation kill rate is strong
- Implementation survives adversarial critique
- Verification properties pass (where defined)

## Prompting Guidance for Builders
When using AI for implementation, enforce this constraint:
- "You are under strict TDD. Write tests first. Do not write implementation until I confirm tests fail. Then write the minimum code to pass one test at a time."

## Output/Artifact Expectations
For each feature, maintain:
- `spec.md`
- `test-plan.md`
- `adversarial-review.md`
- `feedback-integration.md`
- `formal-hardening.md`
- `convergence.md`
- Traceability table: `Spec -> Test -> Implementation -> Review -> Verification`

## When to Use Full VSDD
Use full ceremony for:
- Security-sensitive systems
- Financial/regulated logic
- Critical data integrity workflows
- Multi-model AI-generated code with high correctness needs

For rapid prototypes, apply at minimum:
- Tight spec
- TDD discipline
- One adversarial review pass
````
