# Evaluation plan

This document specifies a proposed experiment. It contains no measured model results.

## 1. Freeze a reviewed dataset version

Complete the factual review needed for the experiment before measuring performance. Keep the exact training, validation and test files, source-family assignments, corpus, tokenizer/model identifiers and adapter configuration. Record the file hashes. The current package is draft version 0.1.0, with a source snapshot of 21 October 2026.

Use the 38 validation examples for development decisions. Reserve the 39 test examples for the final comparison after those decisions are settled. The test set is small and synthetic; it does not represent a statistical sample of all applicants or students.

## 2. Compare systems under matched conditions

The main comparison is:

| System | Model parameters | Evidence and generation settings |
|---|---|---|
| Baseline | Original selected model | Frozen corpus, same retrieval configuration and generation settings |
| Adapted | Same base model with the trained LoRA adapter | The identical corpus, retrieval configuration and generation settings |

An optional third run with the adapter disabled can confirm that the adapter is actually being loaded. Keep hardware and measurement conditions consistent when comparing latency. Do not infer a training benefit from one fluent demonstration answer.

Record the base-model identifier/revision, tokenizer, adapter training settings, number of trainable parameters, training steps, validation-selection rule, and inference settings. Those details make the actual parameter-changing work reviewable. This package does not select a training configuration or guarantee that it fits a particular GPU.

## 3. Separate two evaluation tasks

### A. Answer generation with the supplied context

Run the system/user messages from `test_prompts.jsonl`, then save the generated assistant response by example ID. Use `test.jsonl` only for scoring. Do not append `reference_answer` to the model prompt.

This test asks whether the model can answer, clarify or acknowledge a limitation when the relevant evidence is already supplied. It does not measure the quality of retrieval.

### B. End-to-end retrieval and answering

Start with the question from `retrieval_test.jsonl`, retrieve from the frozen `rag_corpus_en.jsonl`, and construct the answer prompt with the retrieved contexts. Save retrieved IDs, retrieval scores if available, the final answer and timing.

Compare retrieved evidence with `expected_context_ids`. These are the intended source records, not an exhaustive list of every equivalent passage. If another corpus entry supports the same fact, review and document that equivalence. Do not count an irrelevant passage as correct merely because it comes from the same source family. A clarification or missing-information case may need a scoped or limitation-bearing context rather than a direct factual answer.

Report retrieval evidence coverage separately from answer quality. A failure to retrieve the applicable document and a failure to follow a correctly retrieved document have different causes.

## 4. Score each answer

Use a simple, explicit rubric. Preserve the individual criterion scores rather than reporting only one aggregate number.

| Criterion | Score 1 | Score 0 |
|---|---|---|
| Factual grounding | Every material claim is supported by the supplied/retrieved evidence | A material claim is invented, contradicted or overextended |
| Applicability | Correct year, edition, cohort, degree level and route are retained where relevant | An old or route-specific rule is applied to the wrong situation |
| Expected behaviour | Correctly answers, clarifies, identifies missing information or explains the discrepancy | Gives the wrong response type or bypasses a material uncertainty |
| Evidence citation | Cited context IDs exist and support the associated claims | Missing, invented or unsupported evidence references |
| Practical clarity | The response is understandable and addresses the question without a misleading guarantee | Wording is unclear, incomplete in a material way or misleading |

Treat the reference answer as a factual and behavioural guide, not a required exact string. Equivalent English wording should receive the same score. A concise clarification question can be correct without reproducing every sentence of the reference. Citation correctness applies to factual assertions; do not require a source for a purely conversational question that adds no factual claim.

For `historical_answer`, require explicit historical/edition-specific framing. For `conflict`, require the material discrepancy or edition distinction to be preserved and no unsupported resolution. A fully explained policy-version difference need not be described as an unresolved contradiction if the context establishes the dates and scopes.

## 5. Report results transparently

Report counts as well as percentages, including denominators. Show overall results and separate results for ordinary answers, historical answers, clarification, insufficient information and conflict cases. Small categories in a 39-example test should not be interpreted as precise performance estimates.

Useful results include:

- number of answers passing each rubric criterion;
- number of unsupported material claims;
- correct clarification and insufficiency responses;
- correct source/edition/cohort handling;
- retrieval evidence coverage at the chosen result count;
- generation latency under the measured hardware and settings;
- concrete examples of errors that remain after adaptation.

Keep the retrieved evidence and generated text for both systems, so the comparison can be checked. If more than one reviewer scores answers, use the same rubric and record disagreements and their resolution. Do not invent participants, measured improvements or error rates.

## 6. Limits and next evidence

The current contexts are paraphrased workbook summaries and all human source review is pending. A high score would show performance on this small synthetic task under its specific conditions. It would not establish that all underlying university information is current, that real users are satisfied, or that the assistant is reliable for every admission or academic-policy question.

After the prototype experiment, a separately collected set of real applicant/student questions can test transfer beyond rewritten source Q&A. Keep those questions separate from the training set if they are intended for a new final evaluation. User-question collection and the project's survey are separate research activities from this synthetic dataset.
