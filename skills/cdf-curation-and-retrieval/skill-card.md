## Description: <br>
Configures and runs NVIDIA Cosmos Data Factory (CDF) curation and retrieval workflows, covering Cosmos Curator video and image pipelines (split, dedup, shard, annotate) with filtering, captioning, and embedding, Cosmos Dataset Search ingest and search, and TAO data mining embeddings and neighbor matching, including domain event catalogs such as workplace employee conduct monitoring that requires legal review before use. <br>

This skill is ready for commercial/non-commercial use. <br>

## Owner
NVIDIA <br>

### License/Terms of Use: <br>
CC-BY-4.0 AND Apache 2.0 <br>
## Use Case: <br>
Developers, data engineers, and external customer operators use this skill to turn raw video and image collections into curated, training-ready physical AI datasets by configuring, validating, and running Cosmos Curator pipelines through Make, handing embeddings off to TAO Data Mining, and ingesting or searching curated clips in Cosmos Dataset Search. <br>

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
- [calibration-config.md](references/calibration-config.md) <br>
- [capabilities.md](references/capabilities.md) <br>
- [configuration-decision-tree.md](references/configuration-decision-tree.md) <br>
- [context-understanding.md](references/context-understanding.md) <br>
- [cosmos-curator.md](references/cosmos-curator.md) <br>
- [cosmos-dataset-search.md](references/cosmos-dataset-search.md) <br>
- [curation-retrieval-workflow.md](references/curation-retrieval-workflow.md) <br>
- [data-mining.md](references/data-mining.md) <br>
- [distribution-analysis.md](references/distribution-analysis.md) <br>
- [distribution-aware-curation.md](references/distribution-aware-curation.md) <br>
- [ffmpeg-sidecar.md](references/ffmpeg-sidecar.md) <br>
- [gotchas.md](references/gotchas.md) <br>
- [image-curation.md](references/image-curation.md) <br>
- [kpi-metrics.md](references/kpi-metrics.md) <br>
- [restrictive-curation.md](references/restrictive-curation.md) <br>
- [running-pipelines.md](references/running-pipelines.md) <br>
- [sam3-config.md](references/sam3-config.md) <br>
- [video-curation.md](references/video-curation.md) <br>
- [video-lake-curation.md](references/video-lake-curation.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, Configuration instructions, Files, Shell commands] <br>
**Output Format:** [Markdown with status, actions and artifacts, validation evidence, and next steps; inline bash code blocks and flat snake_case YAML pipeline configs] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Responses report a status of ready, completed, blocked, or advisory and never include secret values] <br>

## Evaluation Agents Used: <br>
- Claude Code (`aws/anthropic/bedrock-claude-opus-4-8`) <br>
- Codex (`openai/openai/gpt-5.5`) <br>



## Evaluation Tasks: <br>
13 positive evaluation tasks, 1 attempt per task, each run in an isolated sandbox pod (`k8s-sandbox`) with Skill Evaluator `1.5.6` on 2026-10-14. Overall verdict: FAIL (publication blocked) because Tier 1 static validation failed with 10 findings; Tier 2 semantic deduplication and Tier 3 live agent evaluation passed. <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Security: Is it safe to use? Scored from the `security` signal. <br>
- Correctness: Is the answer correct? Scored from the `accuracy` signal. <br>
- Discoverability: Was the right skill loaded when needed? Scored from the `skill_execution` signal. <br>
- Effectiveness: Did the skill help complete the task? Equal-weight mean of `goal_accuracy` and `behavior_check`. <br>
- Efficiency: Did it avoid wasted tool calls and token usage? Equal-weight mean of `skill_efficiency` and `token_efficiency`. <br>

Underlying evaluation signals used in this run: <br>
- `security`: Unsafe operations, secret leakage, and unauthorized access. <br>
- `skill_execution`: Whether the expected skill was selected, decoys were avoided, and the workflow executed. <br>
- `skill_efficiency`: Tool-call productivity. <br>
- `accuracy`: Final-answer correctness against the reference answer. <br>
- `goal_accuracy`: Whether the user's goal was achieved. <br>
- `behavior_check`: Whether the expected workflow behavior was followed. <br>
- `token_efficiency`: Actual uncached prompt plus completion token usage. <br>



## Evaluation Results: <br>
| Measure | Claude Code (Baseline → Skill Uplift) | Codex (Baseline → Skill Uplift) |
|---|---:|---:|
| Overall | 93.4% (uplift unavailable) | 85.5% (uplift unavailable) |
| Security | 84.6% → 100.0% (+15.4 points) | 92.3% → 92.3% (±0.0 points) |
| Correctness | 47.7% → 98.5% (+50.8 points) | 47.7% → 92.3% (+44.6 points) |
| Discoverability | 83.9% (uplift unavailable) | 68.5% (uplift unavailable) |
| Effectiveness | 43.8% → 93.7% (+49.9 points) | 41.9% → 80.7% (+38.8 points) |
| Efficiency | 91.0% (uplift unavailable) | 93.5% (uplift unavailable) |

## Skill Version(s): <br>
1.2.0 (source: frontmatter, pyproject.toml) <br>

## Ethical Considerations: <br>
NVIDIA believes Trustworthy AI is a shared responsibility and we have established policies and practices to enable development for a wide array of AI applications. When downloaded or used in accordance with our terms of service, developers should work with their internal team to ensure this skill meets requirements for the relevant industry and use case and addresses unforeseen product misuse. <br>

(For Release on NVIDIA Platforms Only) <br>
Please report quality, risk, security vulnerabilities or NVIDIA AI Concerns [here](https://app.intigriti.com/programs/nvidia/nvidiavdp/detail). <br>
