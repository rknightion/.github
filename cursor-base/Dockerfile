# syntax=docker/dockerfile:1@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
FROM ubuntu:24.04@sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b AS ubuntu-base

# The minimal Ubuntu image does not yet carry a TLS trust store. Use the
# checksum-pinned public Ubuntu package to bootstrap the HTTPS apt archive.
FROM ubuntu-base AS bootstrap-ca
ADD --checksum=sha256:f9fbacd417b515450b831032cc39d18059e9874e67525679a43c16071dabf9a0 https://archive.ubuntu.com/ubuntu/pool/main/c/ca-certificates/ca-certificates_20260816ubuntu0.24.04.2_all.deb /tmp/ca-certificates.deb
RUN dpkg-deb -x /tmp/ca-certificates.deb /tmp/ca \
    && cat /tmp/ca/usr/share/ca-certificates/mozilla/*.crt > /tmp/ca-certificates.crt

FROM ubuntu-base

ARG TARGETARCH
ENV PATH=/opt/go/bin:/opt/node/bin:${PATH} \
    GOTOOLCHAIN=auto

COPY --from=bootstrap-ca /tmp/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --chmod=0644 tools.lock /usr/local/share/cursor-base/tools.lock

RUN --mount=type=bind,source=install-tools.sh,target=/tmp/install-tools.sh \
    set -eux; \
    chown root:root /usr/local/share/cursor-base /usr/local/share/cursor-base/tools.lock; \
    chmod 0755 /usr/local/share/cursor-base; \
    chmod 0644 /usr/local/share/cursor-base/tools.lock; \
    export DEBIAN_FRONTEND=noninteractive; \
    mv /etc/apt/sources.list.d/ubuntu.sources /tmp/ubuntu.sources; \
    case "$TARGETARCH" in \
      amd64) archive=https://archive.ubuntu.com/ubuntu/ ;; \
      arm64) archive=https://ports.ubuntu.com/ubuntu-ports/ ;; \
      *) exit 1 ;; \
    esac; \
    printf '%s\n' \
      'Types: deb' \
      "URIs: $archive" \
      'Suites: noble noble-updates noble-security' \
      'Components: main universe' \
      "Architectures: $TARGETARCH" \
      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' > /etc/apt/sources.list.d/build.sources; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -y --no-install-recommends \
      build-essential=12.10ubuntu1 \
      ca-certificates=20260816ubuntu0.24.04.2 \
      curl=8.5.0-2ubuntu10.16 \
      fuse-overlayfs=1.13-1 \
      git=1:2.43.0-1ubuntu7.4 \
      iproute2=6.1.0-1ubuntu6.4 \
      iptables=1.8.10-3ubuntu2 \
      jq=1.7.1-3ubuntu0.24.04.2 \
      libatomic1=14.2.0-4ubuntu2~24.04.1 \
      openssh-client=1:9.6p1-3ubuntu13.20 \
      procps=2:4.0.4-4ubuntu3.3 \
      python3=3.12.3-0ubuntu2.1 \
      python3-venv=3.12.3-0ubuntu2.1 \
      ripgrep=14.1.0-1 \
      shellcheck=0.9.0-1 \
      sudo=1.9.15p5-3ubuntu5.24.04.4 \
      unzip=6.0-28ubuntu4.1 \
      xz-utils=5.6.1+really5.4.5-1ubuntu0.4; \
    bash /tmp/install-tools.sh "$TARGETARCH"; \
    rm -f /etc/apt/sources.list.d/build.sources; \
    mv /tmp/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    update-alternatives --set iptables /usr/sbin/iptables-legacy; \
    update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy; \
    install -d -m 0755 /etc/docker; \
    printf '%s\n' '{"storage-driver":"fuse-overlayfs","features":{"containerd-snapshotter":false}}' > /etc/docker/daemon.json; \
    id -u ubuntu || useradd -m -s /bin/bash ubuntu; \
    groupadd -f docker; \
    usermod -aG docker,sudo ubuntu; \
    printf '%s\n' 'ubuntu ALL=(ALL:ALL) NOPASSWD: ALL' > /etc/sudoers.d/ubuntu; \
    chmod 0440 /etc/sudoers.d/ubuntu; \
    visudo -cf /etc/sudoers.d/ubuntu; \
    node_version="$(node --version)"; \
    fnm_version_dir="/home/ubuntu/.local/share/fnm/node-versions/${node_version}"; \
    mkdir -p "$fnm_version_dir"; \
    ln -s /opt/node "$fnm_version_dir/installation"; \
    chown -hR ubuntu:ubuntu /home/ubuntu/.local

COPY --chmod=0755 smoke.sh /usr/local/bin/cursor-base-smoke
USER ubuntu
WORKDIR /home/ubuntu
CMD ["bash"]
