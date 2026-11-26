# syntax=docker/dockerfile:1
# Shared toolchain for Grafana Assistant coding sandboxes
# (https://grafana.com/docs/grafana-cloud/platform/grafana-assistant/configure/custom-sandbox-images/).
#
# Published as ghcr.io/rknightion/assistant-sandbox-tools by
# .github/workflows/sandbox-image.yml, linux/arm64 only: Grafana sandboxes are ARM64.
# Nothing here runs in a sandbox. The vended .grafana/Dockerfile builds on Grafana's own
# base image and copies /opt/sandbox in, so every tool here is a static or self-contained
# build that does not depend on which Alpine release Grafana's base image uses. Alpine's
# own packages lag the fleet's pins (Go, Python), which is why these come from upstream.
#
# Each download is checked against the checksum its publisher serves beside it.
# Versions are tracked by the custom Renovate manager in renovate.json.

FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
# The fetch stage is thrown away; only the checked downloads below reach the image.
# hadolint ignore=DL3018
RUN apk add --no-cache curl jq tar unzip
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv
WORKDIR /work
RUN mkdir -p /opt/sandbox/bin

# renovate: datasource=golang-version depName=go
ARG GO_VERSION=1.27.4
RUN set -eu; f="go${GO_VERSION}.linux-arm64.tar.gz"; \
    sum="$(curl -fsSL 'https://go.dev/dl/?mode=json&include=all' | jq -r --arg f "$f" '.[].files[] | select(.filename == $f) | .sha256')"; \
    test -n "$sum"; \
    curl -fsSLo go.tgz "https://go.dev/dl/$f"; \
    echo "$sum  go.tgz" | sha256sum -c -; \
    tar -C /opt/sandbox -xzf go.tgz; rm go.tgz; \
    /opt/sandbox/go/bin/go version

# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=v4.3.2
RUN set -eu; f="helm-${HELM_VERSION}-linux-arm64.tar.gz"; \
    curl -fsSLo "$f" "https://get.helm.sh/$f"; \
    echo "$(curl -fsSL "https://get.helm.sh/$f.sha256sum" | cut -d' ' -f1)  $f" | sha256sum -c -; \
    tar -xzf "$f" linux-arm64/helm; install -m 0755 linux-arm64/helm /opt/sandbox/bin/helm; rm -rf "$f" linux-arm64

# renovate: datasource=github-releases depName=opentofu/opentofu
ARG TOFU_VERSION=v1.13.10
RUN set -eu; v="${TOFU_VERSION#v}"; f="tofu_${v}_linux_arm64.tar.gz"; \
    b="https://github.com/opentofu/opentofu/releases/download/v${v}"; \
    curl -fsSLo "$f" "$b/$f"; \
    curl -fsSL "$b/tofu_${v}_SHA256SUMS" | grep "  $f\$" | sha256sum -c -; \
    tar -xzf "$f" tofu; install -m 0755 tofu /opt/sandbox/bin/tofu; rm -f "$f" tofu

# renovate: datasource=github-releases depName=hashicorp/terraform
ARG TERRAFORM_VERSION=v1.17.2
RUN set -eu; v="${TERRAFORM_VERSION#v}"; f="terraform_${v}_linux_arm64.zip"; \
    b="https://releases.hashicorp.com/terraform/${v}"; \
    curl -fsSLo "$f" "$b/$f"; \
    curl -fsSL "$b/terraform_${v}_SHA256SUMS" | grep "  $f\$" | sha256sum -c -; \
    unzip -q "$f" terraform; install -m 0755 terraform /opt/sandbox/bin/terraform; rm -f "$f" terraform

# renovate: datasource=github-releases depName=terraform-linters/tflint
ARG TFLINT_VERSION=v0.66.0
RUN set -eu; f="tflint_linux_arm64.zip"; \
    b="https://github.com/terraform-linters/tflint/releases/download/${TFLINT_VERSION}"; \
    curl -fsSLo "$f" "$b/$f"; \
    curl -fsSL "$b/checksums.txt" | grep "  $f\$" | sha256sum -c -; \
    unzip -q "$f" tflint; install -m 0755 tflint /opt/sandbox/bin/tflint; rm -f "$f" tflint

# renovate: datasource=github-releases depName=kubernetes/kubernetes
ARG KUBECTL_VERSION=v1.37.3
RUN set -eu; b="https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/arm64"; \
    curl -fsSLo kubectl "$b/kubectl"; \
    echo "$(curl -fsSL "$b/kubectl.sha256")  kubectl" | sha256sum -c -; \
    install -m 0755 kubectl /opt/sandbox/bin/kubectl; rm -f kubectl

# renovate: datasource=github-releases depName=rhysd/actionlint
ARG ACTIONLINT_VERSION=v1.7.12
RUN set -eu; v="${ACTIONLINT_VERSION#v}"; f="actionlint_${v}_linux_arm64.tar.gz"; \
    b="https://github.com/rhysd/actionlint/releases/download/v${v}"; \
    curl -fsSLo "$f" "$b/$f"; \
    curl -fsSL "$b/actionlint_${v}_checksums.txt" | grep "  $f\$" | sha256sum -c -; \
    tar -xzf "$f" actionlint; install -m 0755 actionlint /opt/sandbox/bin/actionlint; rm -f "$f" actionlint

# A python-build-standalone musl build: statically linked, so it runs on any Alpine.
# The vended Dockerfile points UV_PYTHON_INSTALL_DIR here, so uv finds it without a download.
# renovate: datasource=python-version depName=python
ARG PYTHON_VERSION=3.15.2
ENV UV_PYTHON_INSTALL_DIR=/opt/sandbox/python
RUN set -eu; uv python install "${PYTHON_VERSION}"; rm -rf /opt/sandbox/python/.temp /opt/sandbox/python/.cache; \
    "$(uv python find "${PYTHON_VERSION}")" --version

FROM scratch
LABEL org.opencontainers.image.source="https://github.com/rknightion/.github" \
      org.opencontainers.image.description="Toolchains copied into rknightion Grafana Assistant sandbox images"
COPY --from=fetch /opt/sandbox/go /opt/sandbox/go
COPY --from=fetch /opt/sandbox/python /opt/sandbox/python
COPY --from=fetch /opt/sandbox/bin /opt/sandbox/bin
