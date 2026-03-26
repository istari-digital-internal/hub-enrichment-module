"""
Hub Enrichment Module — enrich_post function

Istari agent I/O protocol:
  argv[1] = input_file  — path to JSON file written by agent:
              {"post_file": {"type": "user_model", "value": "/path/to/post.md"}}
  argv[2] = output_file — path where this script must write a JSON array:
              [{"name": "enrichment", "type": "file", "value": "/path/to/enrichment.json"}]
  argv[3] = temp_dir    — scratch directory for intermediate files

Environment variables (set on the Istari agent ECS task):
  ANTHROPIC_API_KEY    — Claude API key (required for automated enrichment)
  HUB_CALLBACK_URL     — https://<hub-host>/api/internal/enrichment-complete
  HUB_AGENT_SECRET     — shared secret for Hub callback auth
  GITHUB_PAT           — PAT for ai-hub-content repo (optional; enables git artifact commit)

To switch between automated and manual enrichment:
  - Automated: set ANTHROPIC_API_KEY in AWS Secrets Manager (istari/anthropic-key)
  - Manual:    run /enrich-post <slug> in Claude Code (no API key needed)
"""

import base64
import json
import os
import sys
import logging

import frontmatter
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI research assistant for Istari, an aerospace and defense AI/ML platform company.

You are enriching an internal Hub post — a knowledge-sharing entry from an Istari team member about
an AI agent they built, a Claude skill, a personal workflow, or something interesting they found.

Your job: deeply research the topic, find relevant public resources, and produce structured enrichment
that will help teammates learn from and build on this work.

Produce a JSON object with these fields:
{
  "ai_summary": "2-3 sentence explanation of what was built/discovered and why it matters. Always include at least one sentence on how this relates to or could benefit the Istari team specifically.",
  "generated_prompt": "A replication prompt someone could paste into Claude Code to build something similar. Be specific and actionable. Include suggested tools, patterns, or libraries.",
  "sop_steps": [
    "Step 1: ...",
    "Step 2: ...",
    ...
  ],
  "resources": [
    {
      "title": "Resource title",
      "url": "https://...",
      "relevance": "One sentence explaining why this is useful"
    },
    ...
  ]
}

Guidelines:
- ai_summary: Clear, jargon-appropriate for a technical team. Focus on the "so what". Always include at least one sentence about how this specifically relates to or could benefit Istari (platform, aerospace/defense AI work, team workflows).
- generated_prompt: Should be ready to paste. Use Claude Code / Claude API patterns where relevant.
- sop_steps: 4-8 concrete steps to replicate or build on this. Not generic — specific to this post.
- resources: 3-6 high-quality, publicly accessible links (docs, papers, GitHub repos, blog posts).
  Use web_search to find real, current URLs. Do NOT make up URLs.

Return ONLY the JSON object. No markdown, no explanation outside the JSON."""


def build_research_prompt(title: str, post_type: str, subtype: str, body: str, attachments: list | None = None) -> str:
    attachment_section = ""
    if attachments:
        lines = "\n".join(f"- {a.get('name', '?')} ({a.get('type', '?')}, {a.get('size', 0) // 1024} KB): {a.get('url', '')}"
                          for a in attachments)
        attachment_section = f"\nAttached files (referenced in this post):\n{lines}\n"

    return f"""Post title: {title}
Type: {post_type} / {subtype}
{attachment_section}
Post content:
{body}

Research this post thoroughly. Use web_search to find real, current resources.
Return the enrichment JSON as instructed."""


def run_enrichment(title: str, post_type: str, subtype: str, body: str, attachments: list | None = None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Set it in AWS Secrets Manager (istari/anthropic-key) to enable automated enrichment. "
            "For manual enrichment, use /enrich-post <slug> in Claude Code."
        )

    import anthropic  # deferred import — not required if using manual workflow

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": build_research_prompt(title, post_type, subtype, body, attachments=attachments),
            }
        ],
    )

    # Extract the final text response (after any tool use)
    text_content = ""
    for block in response.content:
        if block.type == "text":
            text_content = block.text
            break

    if not text_content:
        raise ValueError("No text response from Claude")

    # Strip markdown code fences if present
    text = text_content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    return json.loads(text)


def post_callback(post_id: str, enrichment: dict) -> None:
    callback_url = os.environ.get("HUB_CALLBACK_URL")
    agent_secret = os.environ.get("HUB_AGENT_SECRET")
    if not callback_url:
        logger.warning("HUB_CALLBACK_URL not set — skipping Hub callback")
        return

    payload = {"post_id": post_id, **enrichment}
    headers = {"Content-Type": "application/json"}
    if agent_secret:
        headers["Authorization"] = f"Bearer {agent_secret}"

    try:
        resp = requests.post(callback_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        logger.info(f"Hub callback succeeded: {resp.status_code}")
    except Exception as e:
        logger.error(f"Hub callback failed: {e}")
        # Don't raise — enrichment.json artifact still gets uploaded to Istari


def commit_enrichment_to_git(git_path: str, enrichment: dict, pat: str) -> None:
    """
    Commit enrichment.json to the ai-hub-content GitHub repo.

    git_path is the post directory, e.g. "posts/2026-03/my-agent-build".
    The file lands at: posts/2026-03/my-agent-build/enrichment.json

    Non-fatal: if the commit fails, the enrichment is already in the Hub DB.
    """
    owner   = os.environ.get("GITHUB_CONTENT_OWNER", "aframm-ist")
    repo    = os.environ.get("GITHUB_CONTENT_REPO",  "ai-hub-content")
    path    = f"{git_path}/enrichment.json"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Fetch existing SHA if file already exists (required by GitHub API for updates)
    existing = requests.get(api_url, headers=headers, timeout=15)
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    content_b64 = base64.b64encode(
        json.dumps(enrichment, indent=2).encode("utf-8")
    ).decode("ascii")

    verb    = "update" if sha else "create"
    payload = {
        "message":   f"enrichment({verb}): {git_path}",
        "content":   content_b64,
        "branch":    "main",
        "committer": {"name": "istari-ai-hub-bot", "email": "bot@istari-hub"},
        "author":    {"name": "istari-ai-hub-bot", "email": "bot@istari-hub"},
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(api_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    logger.info(f"Committed enrichment.json to git: {git_path} ({verb})")


def get_github_pat() -> str | None:
    """
    Resolve the GitHub PAT.
    Checks GITHUB_PAT env var first, then AWS Secrets Manager (istari/github-pat).
    Returns None if neither is available (git commit will be skipped).
    """
    pat = os.environ.get("GITHUB_PAT")
    if pat:
        return pat

    try:
        import boto3
        sm     = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        secret = json.loads(sm.get_secret_value(SecretId="istari/github-pat")["SecretString"])
        return secret.get("GITHUB_PAT")
    except Exception as e:
        logger.warning(f"Could not fetch GITHUB_PAT from Secrets Manager: {e}")
        return None


def main():
    if len(sys.argv) < 4:
        logger.error("Usage: enrich_post.py <input_file> <output_file> <temp_dir>")
        sys.exit(1)

    input_file  = sys.argv[1]
    output_file = sys.argv[2]
    temp_dir    = sys.argv[3]

    # Read the agent's input JSON to get the actual post.md path
    try:
        with open(input_file, encoding="utf-8") as f:
            inputs = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read input file {input_file}: {e}")
        sys.exit(1)

    post_path = inputs.get("post_file", {}).get("value")
    if not post_path:
        logger.error(f"input_file missing post_file.value: {inputs}")
        sys.exit(1)

    if not os.path.exists(post_path):
        logger.error(f"post.md not found at: {post_path}")
        sys.exit(1)

    # Parse YAML frontmatter + body
    post        = frontmatter.load(post_path)
    title       = post.metadata.get("title", "")
    post_type   = post.metadata.get("post_type", "ibuilt")
    subtype     = post.metadata.get("subtype", "agent")
    post_id     = post.metadata.get("post_id", "")
    git_path    = post.metadata.get("git_path", "")
    body        = post.content
    attachments = post.metadata.get("attachments", None)

    if not title or not body:
        logger.error("post.md missing title or body")
        sys.exit(1)

    logger.info(f"Enriching: {title!r} (post_id={post_id})")

    # ── Automated enrichment (requires ANTHROPIC_API_KEY) ─────────────────────
    try:
        enrichment = run_enrichment(title, post_type, subtype, body, attachments=attachments)
    except RuntimeError as e:
        # API key not configured — log clearly and exit non-zero so job can be retried
        logger.error(str(e))
        sys.exit(1)

    logger.info("Enrichment complete")

    # Write enrichment.json to temp_dir
    enrichment_path = os.path.join(temp_dir, "enrichment.json")
    with open(enrichment_path, "w", encoding="utf-8") as f:
        json.dump(enrichment, f, indent=2)
    logger.info(f"Wrote enrichment artifact: {enrichment_path}")

    # Write the Istari output manifest (JSON array) to output_file
    output_manifest = [
        {
            "name": "enrichment",
            "type": "file",
            "value": enrichment_path,
        }
    ]
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_manifest, f)
    logger.info(f"Wrote output manifest: {output_file}")

    # ── Callback to Hub DB ────────────────────────────────────────────────────
    if post_id:
        post_callback(post_id, enrichment)
    else:
        logger.warning("No post_id in frontmatter — skipping Hub callback")

    # ── Commit enrichment.json to ai-hub-content git repo ────────────────────
    if git_path:
        pat = get_github_pat()
        if pat:
            try:
                commit_enrichment_to_git(git_path, enrichment, pat)
            except Exception as e:
                # Non-fatal: enrichment is already in the Hub DB via callback above
                logger.warning(f"Git commit of enrichment.json failed (non-fatal): {e}")
        else:
            logger.info("GITHUB_PAT not available — skipping git artifact commit")
    else:
        logger.info("No git_path in frontmatter — skipping git artifact commit")


if __name__ == "__main__":
    main()
