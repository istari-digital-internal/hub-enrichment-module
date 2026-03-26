# Hub Enrichment Module

**Module:** `@istari:hub_enrichment`
**Function:** `@istari:enrich_post`
**Version:** 0.1.0

---

## What it does

Automatically enriches posts on the [Istari AI Hub](https://istari-hub.com) — an internal knowledge-sharing platform where team members log AI agents they've built, Claude skills, workflows, and interesting AI developments.

When a post is published, this module:
1. Reads the post content (title, body, type, attachments)
2. Researches the topic using web search
3. Produces structured enrichment:
   - **AI summary** — 2-3 sentence plain-English explanation of what was built and why it matters for the Istari team
   - **Replication prompt** — a ready-to-paste Claude Code prompt someone could use to build something similar
   - **SOP steps** — 4-8 concrete steps to replicate or build on the work
   - **Resources** — 3-6 real, publicly accessible links (docs, papers, repos) found via web search
4. Posts the enrichment back to the Hub via HTTP callback, where it surfaces on the post page

---

## How it works

The module follows the standard Istari agent I/O protocol:

```
python3 hub_enrichment/enrich_post.py <input_file> <output_file> <temp_dir>
```

- **Input:** a `.md` file (Hub post content with YAML frontmatter containing `post_id`, `title`, `post_type`, `subtype`, `git_path`)
- **Output:** `enrichment.json` artifact uploaded to Istari, plus an HTTP callback to the Hub API

The agent runs on ECS Fargate (deployed as `istari-hub-agent`), polling the Istari jobs service for `@istari:enrich_post` jobs dispatched by the Hub's SQS consumer.

### Flow

```
Hub post published
       ↓
  SQS queue (istari-sync)
       ↓
  Lambda (istari-sync/index.py)
  — registers post as Istari Model
  — dispatches @istari:enrich_post job
       ↓
  Istari agent (ECS Fargate)
  — runs enrich_post.py
  — calls Anthropic API + web_search
       ↓
  Hub callback endpoint (/api/internal/enrichment-complete)
  — writes enrichment to DB
  — marks post enrichment_status = complete
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for enrichment |
| `HUB_CALLBACK_URL` | Yes | `https://<hub>/api/internal/enrichment-complete` |
| `HUB_AGENT_SECRET` | Yes | Shared secret for Hub callback auth |
| `GITHUB_PAT` | No | PAT to commit `enrichment.json` to the content repo |

---

## When to use it

This module runs automatically — you don't invoke it manually. It activates whenever a post is published to the Hub and `ANTHROPIC_API_KEY` is set in AWS Secrets Manager (`istari/anthropic-key`).

If you need to manually enrich a post (e.g. re-run enrichment or test without the full pipeline), use the `/enrich-post <slug>` Claude Code skill directly against the Hub database — no API key or agent needed.

---

## Future use cases

The enrichment pattern — read a document, research it, produce structured output, post a callback — is reusable across a range of internal workflows. Some natural extensions:

**Customer-facing deliverables**
- Enrich customer-uploaded models or simulation results with AI-generated analysis, relevant literature, and suggested next steps — same callback pattern, different input schema
- Auto-generate a technical summary and replication guide for any artifact stored in an Istari instance, surfacing it in the platform UI

**Internal knowledge management**
- Extend to Confluence pages or Jira tickets — post published → agent researches → structured summary and related resources attached automatically
- Weekly digest generation: batch-enrich all new Hub posts from the past 7 days into a single digest document dispatched to Slack or email

**CS / deployment support**
- Enrich customer deployment logs or support tickets — agent reads the artifact, cross-references known issues and docs, produces a triage summary
- Pre-call brief generation: given a customer name, pull recent activity and produce a structured brief (similar to the `/customer-brief` skill but running as an Istari job)

**Expanding the enrichment output**
- Add a `demo_script` field — a short walkthrough someone could follow live to demo the built thing
- Add `related_posts` — semantic search against the Hub to surface similar work from other team members
- Add `customer_applicability` — for each active customer, a one-liner on whether and how this is relevant to their use case

All of these follow the same structure: `module_manifest.json` declares the function, an entrypoint script does the work, and a callback delivers results to wherever they're needed.

**A key advantage across all of these use cases: the Istari digital thread.**

Because the agent runs as a registered Istari module, every job is tracked in the platform — who ran it, on what input, when, and what artifact came out. That traceability is automatic. For aerospace and defense workflows where auditability matters, this means every AI-generated analysis, summary, or enrichment has a traceable lineage from input artifact through to output — without any additional logging or audit tooling needed.

---

## Setup

### Prerequisites

- Istari agent binary (`>=9.0.0`)
- Ubuntu 22.04
- Python 3.11+
- Anthropic API key

### Install dependencies

```bash
bash scripts/linux/install.sh
```

### Run locally

```bash
# Build
bash scripts/linux/build.sh

# Test
bash scripts/linux/test_unit.sh

# Clean
bash scripts/linux/clean.sh
```

### Deploy (ECS)

Build and push the Docker image, then set `desiredCount=1` on the `istari-hub-agent` ECS service. The agent will register the module with the Istari jobs service on startup.

```bash
docker build -t istari-hub-agent .
docker tag istari-hub-agent <ecr-repo>/istari-hub-agent:latest
docker push <ecr-repo>/istari-hub-agent:latest
```
