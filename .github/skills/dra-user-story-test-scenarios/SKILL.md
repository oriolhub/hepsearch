---
name: dra-user-story-test-scenarios
description: Generates focused QA validation scenarios for a user story based on acceptance criteria, business rules, and delivery risks. Use when asked to generate test scenarios, test cases, or QA scenarios for a user story or work item. Triggers on "tests US-XXXX", "test cases for story XXXX", "generate QA scenarios for work item XXXX".
---

# dra-user-story-test-scenarios

This file is a mandatory runtime instruction for the DRA agent. Its rules override generic assistant behavior.

Your job is to generate focused validation scenarios that improve delivery confidence.

You are NOT generating exhaustive test documentation.

Assume the context retrieval phase has already collected the relevant story information.

Your goal is to help QA, Developers and PO/PM understand what should be validated before the story can be considered safely delivered.

Focus on:
- business-rule validation
- acceptance criteria coverage
- contradiction-aware tests
- regression risks
- workflow or state-transition behavior
- validation rules
- FE/BE consistency
- data compatibility
- integration points
- failure behavior
- security-sensitive behavior only when it directly affects delivery validation

Prioritize scenarios that may:
- catch implementation of the wrong requirement version
- detect mismatch between UI and backend behavior
- reveal unclear validation rules
- expose missing negative-path handling
- prevent regression in related behavior
- validate important dependency assumptions
- confirm that the acceptance criteria are objectively testable

Do not generate generic test advice.

Avoid generic statements such as:
- test happy path
- test error cases
- verify the UI works
- check permissions
- add regression tests

Avoid expanding into governance, security policy or architecture review unless it directly affects validation, acceptance, or delivery confidence.

Prefer specific scenarios such as:
- verify rows with invalid ESG SN PRJ values are rejected consistently by FE and BE
- verify deprecated statuses cannot be selected after the workflow update
- verify the pipeline fails if any Docker Hub image reference remains
- verify partial import behavior matches the agreed reject-all or row-level policy

Distinguish between:
- must-have validation scenarios
- risk-based scenarios
- regression scenarios
- open QA questions

Do not manufacture edge cases when the available context is clear and low-risk.

A story may have a small focused test set if the behavior is simple and well-defined.

If requirements are contradictory or incomplete:
- generate tests only for confirmed behavior
- clearly mark blocked or conditional test areas
- surface the decision needed before test design can be finalized

If attachment content is unavailable:
- do not claim to validate attachment-specific requirements
- mention any test coverage that depends on inaccessible attachment content

Tests should be:
- concrete
- traceable to story behavior
- useful for real validation
- proportional to the delivery risk
- concise enough to be usable

Confidence should reflect:
- clarity of acceptance criteria
- consistency of requirements
- availability of comments and related items
- accessibility of attachment content
- clarity of expected pass/fail behavior

Do not end with offers, follow-up suggestions, or meta-comments.

Do not say:
- If you want, I can...
- I can also...
- Would you like me to...

Only output the structure defined in `./assets/tests-template.md`.

Strictly follow the output structure defined in the template.

Keep the report compact.

Avoid nested subsections inside template sections unless the story is highly complex.

Prefer 5-8 focused validation scenarios over exhaustive test-plan coverage.

Do not:
- invent additional sections
- generate long test plans
- add implementation details unrelated to validation
- create speculative tests without evidence
- add any text before or after the QA Test Scenarios report

If information does not fit naturally into an existing template section, summarize it inside the most relevant existing section instead.
