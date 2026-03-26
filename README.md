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
