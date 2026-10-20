# Skill Benchmark: cdf-curation-and-retrieval

> ✅ **Overall verdict: PASS — Recommended for publication**

## Publication Recommendation

Recommended for publication based on the completed evaluation evidence in this report.

## Evaluation Metadata

- Skill: `cdf-curation-and-retrieval`
- Evaluation date: 2026-10-20
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
| Overall | 91.8% — baseline ran, but no comparable score was available; uplift unavailable | 85.1% — baseline ran, but no comparable score was available; uplift unavailable |
| Security | 84.6% → 100.0% (+15.4 points) | 96.2% → 96.2% (±0.0 points) |
| Correctness | 46.2% → 100.0% (+53.8 points) | 60.0% → 92.3% (+32.3 points) |
| Discoverability | 86.9% — baseline ran, but no comparable score was available; uplift unavailable | 67.3% — baseline ran, but no comparable score was available; uplift unavailable |
| Effectiveness | 48.3% → 88.4% (+40.1 points) | 42.9% → 77.7% (+34.8 points) |
| Efficiency | 83.7% — baseline ran, but no comparable score was available; uplift unavailable | 92.2% — baseline ran, but no comparable score was available; uplift unavailable |

**How to read this table:** baseline is the same task attempted without the target skill. Scores are rounded to one decimal; threshold-adjacent values use additional precision so their displayed band matches the verdict. Uplift is derived from those displayed scores and shown in percentage points.

Example: `47.0% → 92.0% (+45.0 points)` means the skill-assisted run scored 92.0%, 45.0 percentage points above its 47.0% no-skill baseline.

A partial dimension was calculated from only the available configured signals; review the detailed report before relying on it.

## Token Usage

Actual Tier 3 execution usage is reported for every observed agent/case pair and both conditions.

| Agent | Dataset case | With skill | Without skill | Delta | Change | Coverage |
|---|---|---:|---:|---:|---:|---|
| claude-code | All cases | 3,647,685 | 4,726,544 | -1,078,859 | -22.83% | skill 13/13; base 13/13 |
| claude-code | 1 | 243,608 | 156,115 | +87,493 | +56.04% | skill 1/1; base 1/1 |
| claude-code | 11 | 109,577 | 122,625 | -13,048 | -10.64% | skill 1/1; base 1/1 |
| claude-code | 12 | 61,520 | 30,302 | +31,218 | +103.02% | skill 1/1; base 1/1 |
| claude-code | 13 | 31,529 | 30,872 | +657 | +2.13% | skill 1/1; base 1/1 |
| claude-code | 14 | 246,568 | 149,487 | +97,081 | +64.94% | skill 1/1; base 1/1 |
| claude-code | 15 | 252,090 | 180,739 | +71,351 | +39.48% | skill 1/1; base 1/1 |
| claude-code | 16 | 167,037 | 246,370 | -79,333 | -32.20% | skill 1/1; base 1/1 |
| claude-code | 2 | 247,455 | 150,738 | +96,717 | +64.16% | skill 1/1; base 1/1 |
| claude-code | 3 | 1,789,281 | 2,434,113 | -644,832 | -26.49% | skill 1/1; base 1/1 |
| claude-code | 4 | 116,211 | 277,793 | -161,582 | -58.17% | skill 1/1; base 1/1 |
| claude-code | 5 | 151,104 | 632,537 | -481,433 | -76.11% | skill 1/1; base 1/1 |
| claude-code | 6 | 117,913 | 187,892 | -69,979 | -37.24% | skill 1/1; base 1/1 |
| claude-code | 9 | 113,792 | 126,961 | -13,169 | -10.37% | skill 1/1; base 1/1 |
| codex | All cases | 1,519,421 | 1,474,313 | +45,108 | +3.06% | skill 13/13; base 13/13 |
| codex | 1 | 88,958 | 25,560 | +63,398 | +248.04% | skill 1/1; base 1/1 |
| codex | 11 | 164,913 | 69,549 | +95,364 | +137.12% | skill 1/1; base 1/1 |
| codex | 12 | 13,691 | 13,510 | +181 | +1.34% | skill 1/1; base 1/1 |
| codex | 13 | 14,112 | 104,233 | -90,121 | -86.46% | skill 1/1; base 1/1 |
| codex | 14 | 14,445 | 14,138 | +307 | +2.17% | skill 1/1; base 1/1 |
| codex | 15 | 167,984 | 69,546 | +98,438 | +141.54% | skill 1/1; base 1/1 |
| codex | 16 | 227,646 | 146,411 | +81,235 | +55.48% | skill 1/1; base 1/1 |
| codex | 2 | 130,805 | 114,810 | +15,995 | +13.93% | skill 1/1; base 1/1 |
| codex | 3 | 259,104 | 293,824 | -34,720 | -11.82% | skill 1/1; base 1/1 |
| codex | 4 | 184,960 | 70,063 | +114,897 | +163.99% | skill 1/1; base 1/1 |
| codex | 5 | 67,665 | 377,730 | -310,065 | -82.09% | skill 1/1; base 1/1 |
| codex | 6 | 95,757 | 87,525 | +8,232 | +9.41% | skill 1/1; base 1/1 |
| codex | 9 | 89,381 | 87,414 | +1,967 | +2.25% | skill 1/1; base 1/1 |
| ALL AGENTS | Dataset aggregate | 5,167,106 | 6,200,857 | -1,033,751 | -16.67% | skill 26/26; base 26/26 |

Prompt tokens include cached reads, so total tokens are `prompt + completion` (cached is not added twice). The Efficiency score uses `(prompt - cached) + completion`. N/A means the relevant trajectory counters were not available; coverage is never estimated.

## Tier Status

| Tier | Purpose | Status | Evidence |
|---|---|---|---|
| Tier 1 | Static validation | **PASSED WITH OBSERVATIONS** | 11 validator(s); 11 finding(s) |
| Tier 2 | Semantic deduplication | **PASSED** | 2 validator(s); 0 finding(s) |
| Tier 3 | Live agent evaluation | **PASS** | 2 agent(s); 13 task(s) |

## Findings and Observations

<details>
<summary>Show detailed findings and successful checks</summary>

- **MEDIUM** QUALITY/quality_efficiency: Deeply nested references in calibration-config.md (`skills/cdf-curation-and-retrieval/SKILL.md`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:102`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:103`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:104`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:105`)
- 6 additional finding(s) are available in the full evaluation artifacts.

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
