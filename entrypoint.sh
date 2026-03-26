#!/bin/bash
# Istari agent entrypoint
#
# The agent binary reads from ~/.config/istari_digital/istari_digital_config.yaml
# and exits if the file is missing. This script creates the config file from
# environment variables injected by ECS, then launches the agent.

set -e

CONFIG_DIR="/root/.config/istari_digital"
CONFIG_FILE="${CONFIG_DIR}/istari_digital_config.yaml"

mkdir -p "${CONFIG_DIR}"

# Write config from env vars. Uses both cli: and agent: sections so the
# agent binary finds values regardless of which section it reads.
# headless_mode is set here (not via env var) because the agent binary
# reads this field only from the config file.
cat > "${CONFIG_FILE}" << YAML
cli:
  istari_digital_registry_url: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_URL}"
  istari_digital_registry_auth_token: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_TOKEN}"
  customer_portal_url: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_URL}"
  customer_portal_auth_token: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_TOKEN}"
agent:
  registry_api_url: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_URL}"
  registry_api_token: "${ISTARI_DIGITAL_AGENT_REGISTRY_API_TOKEN}"
  headless_mode: true
YAML

echo "[entrypoint] Config written to ${CONFIG_FILE}"
echo "[entrypoint] Registry URL: ${ISTARI_DIGITAL_AGENT_REGISTRY_API_URL}"
echo "[entrypoint] Starting istari agent..."

exec /opt/local/istari_agent/istari_agent_11.6.6
