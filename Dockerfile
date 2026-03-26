# Istari Hub Enrichment Agent
#
# Bundles the Istari agent (v11.6.6) with the hub_enrichment Python module.
# The agent binary lives at /opt/local/istari_agent/istari_agent_11.6.6
# Modules are loaded from /opt/local/istari_agent/istari_modules/
#
# Build context: istari-module/ directory
# The .deb must be present in the build context (gitignored, 83MB):
#   cp ~/istari-agent_11.6.6_amd64.deb istari-module/
#   docker build -t istari-hub-agent istari-module/
#
# In CI (GitHub Actions), the .deb is downloaded from S3 before docker build.
#
# Required env vars at runtime (from ECS task def / Secrets Manager):
#   ISTARI_DIGITAL_AGENT_REGISTRY_API_URL   — https://fileservice-v2.dev.istari.app
#   ISTARI_DIGITAL_AGENT_REGISTRY_API_TOKEN — PAT from Istari platform settings
#   ISTARI_DIGITAL_AGENT_HEADLESS_MODE      — true (no systray on headless Linux)
#   ANTHROPIC_API_KEY      — Claude API key
#   HUB_CALLBACK_URL       — https://<hub>/api/internal/enrichment-complete
#   HUB_AGENT_SECRET       — shared secret for Hub callback auth
#
# The Istari agent binary reads configuration from a YAML file at:
#   ~/.config/istari_digital/istari_digital_config.yaml
# It does NOT start if this file is missing. The entrypoint script
# creates the file from env vars at container startup.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# System deps + Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Istari agent from bundled .deb
# Installs binary to: /opt/local/istari_agent/istari_agent_11.6.6
# Module directory:   /opt/local/istari_agent/istari_modules/
COPY istari-agent_11.6.6_amd64.deb /tmp/istari-agent.deb
RUN apt-get update && apt-get install -y /tmp/istari-agent.deb \
    && rm /tmp/istari-agent.deb \
    && rm -rf /var/lib/apt/lists/*

# Install hub_enrichment module into the agent's module directory
WORKDIR /opt/local/istari_agent/istari_modules
RUN mkdir -p hub_enrichment/hub_enrichment

COPY module_manifest.json ./hub_enrichment/
COPY hub_enrichment/ ./hub_enrichment/hub_enrichment/
COPY requirements.txt ./hub_enrichment/

# Install Python deps
RUN pip3 install --no-cache-dir -r hub_enrichment/requirements.txt

# Convenience symlink for the agent binary
RUN ln -s /opt/local/istari_agent/istari_agent_11.6.6 /usr/local/bin/istari-agent

# Entrypoint script: creates istari_digital_config.yaml from env vars,
# then launches the agent binary. The agent only starts if the config
# file already exists — it exits silently if it creates a new default.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /opt/local/istari_agent

ENTRYPOINT ["/entrypoint.sh"]
