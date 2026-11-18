# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS ubuntu-base

# The minimal Ubuntu image does not yet carry a TLS trust store. Use the
# checksum-pinned public Ubuntu package to bootstrap the HTTPS apt snapshot.
FROM ubuntu-base AS bootstrap-ca
ADD --checksum=sha256:f9fbacd417b515450b831032cc39d18059e9874e67525679a43c16071dabf9a0 https://snapshot.ubuntu.com/ubuntu/20261117T000000Z/pool/main/c/ca-certificates/ca-certificates_20260816ubuntu0.24.04.2_all.deb /tmp/ca-certificates.deb
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
    printf '%s\n' \
      'Types: deb' \
      'URIs: https://snapshot.ubuntu.com/ubuntu/20261117T000000Z/' \
      'Suites: noble noble-updates noble-security' \
      'Components: main universe' \
      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
      'Check-Valid-Until: no' > /etc/apt/sources.list.d/snapshot.sources; \
    apt-get -o APT::Update::Error-Mode=any update; \
    apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl fuse-overlayfs git iproute2 iptables \
      jq libatomic1 openssh-client procps python3 python3-venv ripgrep shellcheck sudo unzip xz-utils; \
    bash /tmp/install-tools.sh "$TARGETARCH"; \
    rm -f /etc/apt/sources.list.d/snapshot.sources; \
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
