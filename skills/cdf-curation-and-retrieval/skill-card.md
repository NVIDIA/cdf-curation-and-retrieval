## Description: <br>
Configures and runs NVIDIA Cosmos Data Factory (CDF) curation and retrieval workflows, covering Cosmos Curator video and image pipelines (split, dedup, shard, annotate) with filtering, captioning, and embedding, Cosmos Dataset Search ingest, search, and capability qualification, and TAO data mining embedding and neighbor-matching handoffs. <br>

This skill is ready for commercial/non-commercial use. <br>

## Owner
NVIDIA <br>

### License/Terms of Use: <br>
CC-BY-4.0 AND Apache 2.0 <br>
## Use Case: <br>
Developers, ML/data engineers, and operators (internal and external) use this skill to turn raw video and image collections into curated, training-ready physical AI datasets by configuring, validating, and running Cosmos Curator pipelines, KPI-driven and distribution-aware curation, Cosmos Dataset Search ingest/search, and TAO data mining handoffs through the repository's Make targets. Workplace employee conduct monitoring catalogs require confirmed legal review, a lawful basis, and any required worker notice before use. <br>

### Deployment Geography for Use: <br>
Global <br>

## Requirements / Dependencies: <br>
**Requires API Key or External Credential:** [Yes] <br>
**Credential Type(s):** [Cloud Credentials, API key] <br>

Do not include secrets in prompts/logs/output; use least-privilege credentials; rotate keys as appropriate. <br>

## Known Risks and Mitigations: <br>
Risk: Review before execution as proposals could introduce incorrect or misleading guidance into skills. <br>
Mitigation: Review and scan skill before deployment. <br>

## Reference(s): <br>
- [Calibration Config](references/calibration-config.md) <br>
- [Capabilities](references/capabilities.md) <br>
- [Configuration Decision Tree](references/configuration-decision-tree.md) <br>
- [Context Understanding](references/context-understanding.md) <br>
- [Cosmos Curator](references/cosmos-curator.md) <br>
- [Cosmos Dataset Search](references/cosmos-dataset-search.md) <br>
- [Curation-Retrieval Workflow](references/curation-retrieval-workflow.md) <br>
- [Data Mining](references/data-mining.md) <br>
- [Distribution Analysis](references/distribution-analysis.md) <br>
- [Distribution-Aware Curation](references/distribution-aware-curation.md) <br>
- [FFmpeg Sidecar](references/ffmpeg-sidecar.md) <br>
- [Gotchas](references/gotchas.md) <br>
- [Image Curation](references/image-curation.md) <br>
- [KPI Metrics](references/kpi-metrics.md) <br>
- [Restrictive Curation](references/restrictive-curation.md) <br>
- [Running Pipelines](references/running-pipelines.md) <br>
- [SAM3 Config](references/sam3-config.md) <br>
- [Video Curation](references/video-curation.md) <br>
- [Video Lake Curation](references/video-lake-curation.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, Configuration instructions, Files, Shell commands] <br>
**Output Format:** [Markdown status report (ready, completed, blocked, or advisory) with inline bash code blocks and flat snake_case YAML pipeline configs] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Execution and collection-changing commands run only after config preflight and explicit user authorization; secret values are never included in output.] <br>

## Evaluation Agents Used: <br>
- Claude Code (`aws/anthropic/bedrock-claude-opus-4-8`) <br>
- Codex (`openai/openai/gpt-5.5`) <br>



## Evaluation Tasks: <br>
13 positive evaluation tasks (dataset digest `sha256:fdcbcab3028d167dee02acf67b997dfc3fa3f6fb481a0a536d92378a5b28acaf`), one attempt per task, each run in an isolated `k8s-sandbox` pod and compared against a no-skill baseline; evaluated 2026-10-20 with evaluator version `1.5.6`. Overall verdict: PASS. <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Security: Is it safe to use? Scored from the `security` signal. <br>
- Correctness: Is the answer correct? Scored from the `accuracy` signal. <br>
- Discoverability: Was the right skill loaded when needed? Scored from the `skill_execution` signal. <br>
- Effectiveness: Did the skill help complete the task? Equal-weight mean of `goal_accuracy` and `behavior_check`. <br>
- Efficiency: Did it avoid wasted tool calls and token usage? 50% `skill_efficiency` plus 50% `token_efficiency`. <br>

Underlying evaluation signals used in this run: <br>
- `security`: Unsafe operations, secret leakage, and unauthorized access. <br>
- `skill_execution`: Whether the expected skill was selected, decoys were avoided, and the workflow executed. <br>
- `skill_efficiency`: Tool-call productivity (legacy wire id; routing is scored under Discoverability). <br>
- `accuracy`: Final-answer correctness against the reference answer. <br>
- `goal_accuracy`: Whether the user's goal was achieved. <br>
- `behavior_check`: Whether the expected workflow behavior was followed. <br>
- `token_efficiency`: Actual uncached prompt plus completion usage (50% of Efficiency). <br>



## Evaluation Results: <br>
| Measure | Claude Code (Baseline → Skill Uplift) | Codex (Baseline → Skill Uplift) |
|---|---:|---:|
| Overall | 91.8% — baseline ran, but no comparable score was available; uplift unavailable | 85.1% — baseline ran, but no comparable score was available; uplift unavailable |
| Security | 84.6% → 100.0% (+15.4 points) | 96.2% → 96.2% (±0.0 points) |
| Correctness | 46.2% → 100.0% (+53.8 points) | 60.0% → 92.3% (+32.3 points) |
| Discoverability | 86.9% — baseline ran, but no comparable score was available; uplift unavailable | 67.3% — baseline ran, but no comparable score was available; uplift unavailable |
| Effectiveness | 48.3% → 88.4% (+40.1 points) | 42.9% → 77.7% (+34.8 points) |
| Efficiency | 83.7% — baseline ran, but no comparable score was available; uplift unavailable | 92.2% — baseline ran, but no comparable score was available; uplift unavailable |

## Skill Version(s): <br>
1.2.0 (source: frontmatter, pyproject.toml) <br>

## Ethical Considerations: <br>
NVIDIA believes Trustworthy AI is a shared responsibility and we have established policies and practices to enable development for a wide array of AI applications. When downloaded or used in accordance with our terms of service, developers should work with their internal team to ensure this skill meets requirements for the relevant industry and use case and addresses unforeseen product misuse. <br>

(For Release on NVIDIA Platforms Only) <br>
Please report quality, risk, security vulnerabilities or NVIDIA AI Concerns [here](https://app.intigriti.com/programs/nvidia/nvidiavdp/detail). <br>
