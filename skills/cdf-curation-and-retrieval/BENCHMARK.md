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
- Dataset digest: `sha256:7cb5ca235cc988433ce2a110f837664c9aaacd412e9b5fb8589ce89b4a6d7499` (skill-evaluator-dataset-snapshot/1)
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
| Overall | 93.1% — baseline ran, but no comparable score was available; uplift unavailable | 87.0% — baseline ran, but no comparable score was available; uplift unavailable |
| Security | 92.3% → 100.0% (+7.7 points) | 100.0% → 100.0% (±0.0 points) |
| Correctness | 43.1% → 100.0% (+56.9 points) | 49.2% → 90.8% (+41.6 points) |
| Discoverability | 83.5% — baseline ran, but no comparable score was available; uplift unavailable | 70.8% — baseline ran, but no comparable score was available; uplift unavailable |
| Effectiveness | 45.7% → 93.1% (+47.4 points) | 39.5% → 78.7% (+39.2 points) |
| Efficiency | 88.9% — baseline ran, but no comparable score was available; uplift unavailable | 94.8% — baseline ran, but no comparable score was available; uplift unavailable |

**How to read this table:** baseline is the same task attempted without the target skill. Scores are rounded to one decimal; threshold-adjacent values use additional precision so their displayed band matches the verdict. Uplift is derived from those displayed scores and shown in percentage points.

Example: `47.0% → 92.0% (+45.0 points)` means the skill-assisted run scored 92.0%, 45.0 percentage points above its 47.0% no-skill baseline.

A partial dimension was calculated from only the available configured signals; review the detailed report before relying on it.

## Token Usage

Actual Tier 3 execution usage is reported for every observed agent/case pair and both conditions.

| Agent | Dataset case | With skill | Without skill | Delta | Change | Coverage |
|---|---|---:|---:|---:|---:|---|
| claude-code | All cases | 3,123,932 | 3,148,128 | -24,196 | -0.77% | skill 13/13; base 13/13 |
| claude-code | 1 | 117,960 | 124,734 | -6,774 | -5.43% | skill 1/1; base 1/1 |
| claude-code | 11 | 109,724 | 184,920 | -75,196 | -40.66% | skill 1/1; base 1/1 |
| claude-code | 12 | 30,521 | 30,146 | +375 | +1.24% | skill 1/1; base 1/1 |
| claude-code | 13 | 31,345 | 30,705 | +640 | +2.08% | skill 1/1; base 1/1 |
| claude-code | 14 | 246,444 | 179,919 | +66,525 | +36.97% | skill 1/1; base 1/1 |
| claude-code | 15 | 291,946 | 149,225 | +142,721 | +95.64% | skill 1/1; base 1/1 |
| claude-code | 16 | 225,161 | 526,825 | -301,664 | -57.26% | skill 1/1; base 1/1 |
| claude-code | 2 | 300,500 | 184,367 | +116,133 | +62.99% | skill 1/1; base 1/1 |
| claude-code | 3 | 1,168,078 | 576,597 | +591,481 | +102.58% | skill 1/1; base 1/1 |
| claude-code | 4 | 111,781 | 219,807 | -108,026 | -49.15% | skill 1/1; base 1/1 |
| claude-code | 5 | 106,650 | 562,737 | -456,087 | -81.05% | skill 1/1; base 1/1 |
| claude-code | 6 | 270,052 | 217,805 | +52,247 | +23.99% | skill 1/1; base 1/1 |
| claude-code | 9 | 113,770 | 160,341 | -46,571 | -29.04% | skill 1/1; base 1/1 |
| codex | All cases | 1,432,390 | 1,096,865 | +335,525 | +30.59% | skill 13/13; base 13/13 |
| codex | 1 | 89,825 | 66,604 | +23,221 | +34.86% | skill 1/1; base 1/1 |
| codex | 11 | 89,936 | 113,100 | -23,164 | -20.48% | skill 1/1; base 1/1 |
| codex | 12 | 13,695 | 13,545 | +150 | +1.11% | skill 1/1; base 1/1 |
| codex | 13 | 112,888 | 13,976 | +98,912 | +707.73% | skill 1/1; base 1/1 |
| codex | 14 | 14,432 | 14,504 | -72 | -0.50% | skill 1/1; base 1/1 |
| codex | 15 | 72,453 | 69,638 | +2,815 | +4.04% | skill 1/1; base 1/1 |
| codex | 16 | 174,597 | 148,945 | +25,652 | +17.22% | skill 1/1; base 1/1 |
| codex | 2 | 110,978 | 129,878 | -18,900 | -14.55% | skill 1/1; base 1/1 |
| codex | 3 | 307,677 | 226,659 | +81,018 | +35.74% | skill 1/1; base 1/1 |
| codex | 4 | 97,493 | 69,491 | +28,002 | +40.30% | skill 1/1; base 1/1 |
| codex | 5 | 93,007 | 69,324 | +23,683 | +34.16% | skill 1/1; base 1/1 |
| codex | 6 | 143,900 | 42,220 | +101,680 | +240.83% | skill 1/1; base 1/1 |
| codex | 9 | 111,509 | 118,981 | -7,472 | -6.28% | skill 1/1; base 1/1 |
| ALL AGENTS | Dataset aggregate | 4,556,322 | 4,244,993 | +311,329 | +7.33% | skill 26/26; base 26/26 |

Prompt tokens include cached reads, so total tokens are `prompt + completion` (cached is not added twice). The Efficiency score uses `(prompt - cached) + completion`. N/A means the relevant trajectory counters were not available; coverage is never estimated.

## Tier Status

| Tier | Purpose | Status | Evidence |
|---|---|---|---|
| Tier 1 | Static validation | **PASSED WITH OBSERVATIONS** | 11 validator(s); 10 finding(s) |
| Tier 2 | Semantic deduplication | **PASSED WITH OBSERVATIONS** | 2 validator(s); 1 finding(s) |
| Tier 3 | Live agent evaluation | **PASS** | 2 agent(s); 13 task(s) |

## Findings and Observations

<details>
<summary>Show detailed findings and successful checks</summary>

- **HIGH** DUPLICATE/duplicate: Duplicate content found across references/cosmos-dataset-search.md and references/curation-retrieval-workflow.md:
  "## Public GA bulk-ingest workflow" in references/cosmos-dataset-search.md (lines 98-131)
  vs "### 2. Send CE1 to CDS" in references/curation-retrieval-workflow.md (lines 30-63) (`references/cosmos-dataset-search.md:98`)
- **MEDIUM** QUALITY/quality_efficiency: Deeply nested references in calibration-config.md (`skills/cdf-curation-and-retrieval/SKILL.md`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:102`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:103`)
- **MEDIUM** SECURITY/Skill Enumeration (AS3): Agent Snooping: skills/cdf-curation-and-retrieval/SKILL.md (`BENCHMARK.md:104`)
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
