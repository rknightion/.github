#!/usr/bin/env bash
set -euo pipefail

arch=${1:?expected a native Linux architecture}
if [[ "$arch" != "$(dpkg --print-architecture)" ]]; then
    printf 'Package architecture does not match the build platform: %s\n' "$arch" >&2
    exit 1
fi
case "$arch" in
    amd64) machine=x86_64; node_arch=x64; fnm_asset=fnm-linux.zip ;;
    arm64) machine=aarch64; node_arch=arm64; fnm_asset=fnm-arm64.zip ;;
    *) printf 'Unsupported architecture: %s\n' "$arch" >&2; exit 1 ;;
esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
chmod 0755 "$work"
cd "$work"
packages=()

download() {
    local url="$1" file="$2" checksum="$3"
    curl -q --fail --silent --show-error --location --retry 3 \
        --proto '=https' --proto-redir '=https' --output "$file" "$url"
    printf '%s  %s\n' "$checksum" "$file" | sha256sum --check --strict -
}

while read -r tool version amd64_sha arm64_sha; do
    [[ -n "$tool" && "$tool" != \#* ]] || continue
    checksum="$amd64_sha"
    if [[ "$arch" == arm64 ]]; then
        checksum="$arm64_sha"
    fi

    member=
    case "$tool" in
        go)
            file="go${version}.linux-${arch}.tar.gz"
            url="https://go.dev/dl/${file}"
            ;;
        node)
            prefix="node-v${version}-linux-${node_arch}"
            file="${prefix}.tar.xz"
            url="https://nodejs.org/dist/v${version}/${file}"
            ;;
        fnm)
            file="$fnm_asset"
            url="https://github.com/Schniz/fnm/releases/download/v${version}/${file}"
            ;;
        uv)
            prefix="uv-${machine}-unknown-linux-gnu"
            file="${prefix}.tar.gz"
            url="https://github.com/astral-sh/uv/releases/download/${version}/${file}"
            member="${prefix}/uv"
            ;;
        python)
            # Must follow uv in tools.lock. uv also checks its own embedded digest.
            build="${version#*+}"
            file="cpython-${version}-${machine}-unknown-linux-gnu-install_only_stripped.tar.gz"
            url="https://github.com/astral-sh/python-build-standalone/releases/download/${build}/${file/+/%2B}"
            mkdir -p "python-mirror/$build"
            file="python-mirror/$build/$file"
            ;;
        just)
            file="just-${version}-${machine}-unknown-linux-musl.tar.gz"
            url="https://github.com/casey/just/releases/download/${version}/${file}"
            member=just
            ;;
        gh)
            prefix="gh_${version}_linux_${arch}"
            file="${prefix}.tar.gz"
            url="https://github.com/cli/cli/releases/download/v${version}/${file}"
            member="${prefix}/bin/gh"
            ;;
        actionlint)
            file="actionlint_${version}_linux_${arch}.tar.gz"
            url="https://github.com/rhysd/actionlint/releases/download/v${version}/${file}"
            member=actionlint
            ;;
        zizmor)
            file="zizmor-${machine}-unknown-linux-gnu.tar.gz"
            url="https://github.com/zizmorcore/zizmor/releases/download/v${version}/${file}"
            member=zizmor
            ;;
        docker-ce|docker-ce-cli|containerd.io|docker-buildx-plugin|docker-compose-plugin)
            file="${tool}_${version}~ubuntu.24.04~noble_${arch}.deb"
            url="https://download.docker.com/linux/ubuntu/dists/noble/pool/stable/${arch}/${file}"
            ;;
        *) printf 'Unknown pinned tool: %s\n' "$tool" >&2; exit 1 ;;
    esac
    download "$url" "$file" "$checksum"

    case "$tool" in
        go)
            # The upstream test key is used by the macOS and Windows verifier tests.
            tar --anchored --no-wildcards --exclude='go/src/crypto/x509/platform_root_key.pem' \
                -xzf "$file" -C /opt
            ;;
        node)
            install -d -m 0755 /opt/node
            tar -xJf "$file" -C /opt/node --strip-components=1
            ;;
        fnm) unzip -p "$file" fnm > fnm.bin; install -m 0755 fnm.bin /usr/local/bin/fnm ;;
        python)
            # Installed in the user's default uv directory so uv can still add
            # other versions there. The Dockerfile hands ~/.local to ubuntu.
            id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu
            UV_CACHE_DIR="$work/uv-cache" \
                UV_PYTHON_INSTALL_DIR=/home/ubuntu/.local/share/uv/python \
                UV_PYTHON_INSTALL_MIRROR="file://$work/python-mirror" \
                uv python install --no-bin "cpython-${version%+*}-linux-${machine}-gnu"
            ;;
        docker-ce|docker-ce-cli|containerd.io|docker-buildx-plugin|docker-compose-plugin)
            packages+=("./$file")
            continue
            ;;
        *)
            tar -xOzf "$file" "$member" > "$tool"
            install -m 0755 "$tool" "/usr/local/bin/$tool"
            if [[ "$tool" == uv ]]; then
                tar -xOzf "$file" "${prefix}/uvx" > uvx
                install -m 0755 uvx /usr/local/bin/uvx
            fi
            ;;
    esac
    rm "$file"
done < /usr/local/share/cursor-base/tools.lock

# apt resolves the Ubuntu dependencies from the signed snapshot. The Docker debs
# themselves were checked above and the Ubuntu image's policy-rc.d blocks startup.
apt-get install -y --no-install-recommends "${packages[@]}"

# The upstream service script aborts if the VM cannot raise these limits.
# Inherit the VM's limits when a change is unavailable.
sed -Ei 's/^([[:space:]]*ulimit (-Hn 524288|-[up] unlimited))$/\1 2>\/dev\/null || true/' \
    /etc/init.d/docker
