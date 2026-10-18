# Skill Benchmark: cdf-curation-and-retrieval

> ❌ **Overall verdict: FAIL — Publication blocked**

The skill should be reviewed before publication. Address the blocking findings below, then rerun Skill Evaluator.

## Evaluation Metadata

- Skill: `cdf-curation-and-retrieval`
- Evaluation date: 2026-10-14
- Evaluator version: `1.5.6`
- Agents: Claude Code (`aws/anthropic/bedrock-claude-opus-4-8`), Codex (`openai/openai/gpt-5.5`)
- Tasks: 13 evaluation tasks (13 positive)
- Dataset digest: `sha256:fdcbcab3028d167dee02acf67b997dfc3fa3f6fb481a0a536d92378a5b28acaf` (skill-evaluator-dataset-snapshot/1)
- Attempts per task: 1
- Environment: `k8s-sandbox`
- Tier 2 evidence: required for publication
- Tier 3 evidence: required for publication

Each task attempt ran in its own isolated sandbox pod.

## What This Report Answers

The three-tier evaluation checks whether the skill:

- is safe to use;
- produces correct answers;
- is discovered and activated when needed;
- helps the agent complete the user's goal and expected workflow; and
- avoids wasted skill and tool usage.

## Results at a Glance

| Measure | Claude Code (Baseline → Skill Uplift) | Codex (Baseline → Skill Uplift) |
|---|---:|---:|
| Overall | 93.4% — baseline ran, but no comparable score was available; uplift unavailable | 85.5% — baseline ran, but no comparable score was available; uplift unavailable |
| Security | 84.6% → 100.0% (+15.4 points) | 92.3% → 92.3% (±0.0 points) |
| Correctness | 47.7% → 98.5% (+50.8 points) | 47.7% → 92.3% (+44.6 points) |
| Discoverability | 83.9% — baseline ran, but no comparable score was available; uplift unavailable | 68.5% — baseline ran, but no comparable score was available; uplift unavailable |
| Effectiveness | 43.8% → 93.7% (+49.9 points) | 41.9% → 80.7% (+38.8 points) |
| Efficiency | 91.0% — baseline ran, but no comparable score was available; uplift unavailable | 93.5% — baseline ran, but no comparable score was available; uplift unavailable |

**How to read this table:** baseline is the same task attempted without the target skill. Scores are rounded to one decimal; threshold-adjacent values use additional precision so their displayed band matches the verdict. Uplift is derived from those displayed scores and shown in percentage points.

Example: `47.0% → 92.0% (+45.0 points)` means the skill-assisted run scored 92.0%, 45.0 percentage points above its 47.0% no-skill baseline.

A partial dimension was calculated from only the available configured signals; review the detailed report before relying on it.

## Token Usage

Actual Tier 3 execution usage is reported for every observed agent/case pair and both conditions.

| Agent | Dataset case | With skill | Without skill | Delta | Change | Coverage |
|---|---|---:|---:|---:|---:|---|
| claude-code | All cases | 2,965,079 | 3,433,510 | -468,431 | -13.64% | skill 13/13; base 13/13 |
| claude-code | 1 | 200,399 | 185,988 | +14,411 | +7.75% | skill 1/1; base 1/1 |
| claude-code | 11 | 109,369 | 249,077 | -139,708 | -56.09% | skill 1/1; base 1/1 |
| claude-code | 12 | 30,555 | 61,520 | -30,965 | -50.33% | skill 1/1; base 1/1 |
| claude-code | 13 | 30,612 | 30,594 | +18 | +0.06% | skill 1/1; base 1/1 |
| claude-code | 14 | 246,395 | 148,849 | +97,546 | +65.53% | skill 1/1; base 1/1 |
| claude-code | 15 | 213,545 | 210,736 | +2,809 | +1.33% | skill 1/1; base 1/1 |
| claude-code | 16 | 113,581 | 213,820 | -100,239 | -46.88% | skill 1/1; base 1/1 |
| claude-code | 2 | 296,111 | 248,885 | +47,226 | +18.98% | skill 1/1; base 1/1 |
| claude-code | 3 | 1,134,492 | 798,666 | +335,826 | +42.05% | skill 1/1; base 1/1 |
| claude-code | 4 | 111,612 | 450,888 | -339,276 | -75.25% | skill 1/1; base 1/1 |
| claude-code | 5 | 146,627 | 584,744 | -438,117 | -74.92% | skill 1/1; base 1/1 |
| claude-code | 6 | 218,186 | 154,525 | +63,661 | +41.20% | skill 1/1; base 1/1 |
| claude-code | 9 | 113,595 | 95,218 | +18,377 | +19.30% | skill 1/1; base 1/1 |
| codex | All cases | 1,827,607 | 1,629,164 | +198,443 | +12.18% | skill 13/13; base 13/13 |
| codex | 1 | 90,988 | 67,192 | +23,796 | +35.41% | skill 1/1; base 1/1 |
| codex | 11 | 113,108 | 84,354 | +28,754 | +34.09% | skill 1/1; base 1/1 |
| codex | 12 | 13,777 | 13,581 | +196 | +1.44% | skill 1/1; base 1/1 |
| codex | 13 | 14,275 | 14,010 | +265 | +1.89% | skill 1/1; base 1/1 |
| codex | 14 | 13,819 | 13,939 | -120 | -0.86% | skill 1/1; base 1/1 |
| codex | 15 | 92,385 | 115,256 | -22,871 | -19.84% | skill 1/1; base 1/1 |
| codex | 16 | 152,597 | 84,853 | +67,744 | +79.84% | skill 1/1; base 1/1 |
| codex | 2 | 94,493 | 183,384 | -88,891 | -48.47% | skill 1/1; base 1/1 |
| codex | 3 | 743,887 | 385,325 | +358,562 | +93.05% | skill 1/1; base 1/1 |
| codex | 4 | 193,223 | 69,807 | +123,416 | +176.80% | skill 1/1; base 1/1 |
| codex | 5 | 91,118 | 383,380 | -292,262 | -76.23% | skill 1/1; base 1/1 |
| codex | 6 | 141,313 | 85,532 | +55,781 | +65.22% | skill 1/1; base 1/1 |
| codex | 9 | 72,624 | 128,551 | -55,927 | -43.51% | skill 1/1; base 1/1 |
| ALL AGENTS | Dataset aggregate | 4,792,686 | 5,062,674 | -269,988 | -5.33% | skill 26/26; base 26/26 |

Prompt tokens include cached reads, so total tokens are `prompt + completion` (cached is not added twice). The Efficiency score uses `(prompt - cached) + completion`. N/A means the relevant trajectory counters were not available; coverage is never estimated.

## Tier Status

| Tier | Purpose | Status | Evidence |
|---|---|---|---|
| Tier 1 | Static validation | **FAILED** | 11 validator(s); 10 finding(s) |
| Tier 2 | Semantic deduplication | **PASSED** | 2 validator(s); 0 finding(s) |
| Tier 3 | Live agent evaluation | **PASS** | 2 agent(s); 13 task(s) |

## Findings and Observations

<details>
<summary>Show detailed findings and successful checks</summary>

- **MEDIUM** QUALITY/quality_efficiency: Deeply nested references in calibration-config.md (`skills/cdf-curation-and-retrieval/SKILL.md`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:101`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:102`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:103`)
- **MEDIUM** SECURITY/Autonomous Decision Making (EA2): Excessive Agency: Without confirmation (`BENCHMARK.md:104`)
- 5 additional finding(s) are available in the full evaluation artifacts.

</details>

## Scoring Methodology

<details>
<summary>Show dimension definitions, source signals, and thresholds</summary>

| Dimension | Question | Scored signals |
|---|---|---|
| Security | Is it safe to use? | `security` (100%) |
| Correctness | Is the answer correct? | `accuracy` (100%) |
| Discoverability | Was the right skill loaded when needed? | `skill_execution` (100%) |
| Effectiveness | Did the skill help complete the task? | `goal_accuracy` (50%) + `behavior_check` (50%) |
| Efficiency | Did it avoid wasted tool calls and token usage? | `skill_efficiency` (50%) + `token_efficiency` (50%) |

- Dimension bands: PASS at 50% or above; NEUTRAL from 40% to below 50%; FAIL below 40%.
- Overall Tier 3 lift: PASS at +5 points or more; FAIL at -10 points or less; values between those bands are NEUTRAL.
- Overall verdict: PASS only when every configured dimension passes for at least one supported agent. Lift is reported as diagnostic evidence and does not override this gate.
- The 50% attempt pass threshold is a separate per-task gate; it is not the dimension pass threshold.
- Effectiveness is the equal-weight mean of goal completion (`goal_accuracy`) and expected workflow adherence (`behavior_check`).
- Efficiency is 50% tool-call productivity (the backward-compatible `skill_efficiency` wire id) and 50% `token_efficiency`. Positive-case skill routing is scored under Discoverability, not Efficiency; a negative case without a routing target is N/A. N/A sources are omitted, remaining weights are renormalized, and the dimension is marked partial.

Signals present in this run:

- `security` (Security): unsafe operations, secret leakage, and unauthorized access.
- `skill_execution` (Skill Execution): whether the expected skill was selected, decoys were avoided, and the workflow executed.
- `skill_efficiency` (Tool Productivity): tool-call productivity (legacy wire id; routing is scored under Discoverability).
- `accuracy` (Accuracy): final-answer correctness against the reference answer.
- `goal_accuracy` (Goal Accuracy): whether the user's goal was achieved.
- `behavior_check` (Behavior Check): whether the expected workflow behavior was followed.
- `token_efficiency` (Token Efficiency): actual uncached prompt plus completion usage (50% of Efficiency).

</details>

## Freshness

Regenerate this benchmark when the skill, evaluation dataset, target agent/model, evaluator version, environment, or scoring policy changes.
