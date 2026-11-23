#!/usr/bin/env bash
set -euo pipefail

arch=${1:?usage: cursor-base-smoke <amd64|arm64> [--docker]}
mode=${2:-}
[[ -z "$mode" || "$mode" == --docker ]]

assert_equal() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$expected" != "$actual" ]]; then
        printf '%s: expected %s, got %s\n' "$label" "$expected" "$actual" >&2
        exit 1
    fi
    printf '%s: %s\n' "$label" "$actual"
}

case "$arch" in
    amd64) machine=x86_64 ;;
    arm64) machine=aarch64 ;;
    *) printf 'Unsupported architecture: %s\n' "$arch" >&2; exit 1 ;;
esac
assert_equal architecture "$machine" "$(uname -m)"
assert_equal package-architecture "$arch" "$(dpkg --print-architecture)"
assert_equal user ubuntu "$(id -un)"
assert_equal sudo 0 "$(sudo -n id -u)"
id -Gn | tr ' ' '\n' | grep -x docker
test ! -e /opt/go/src/crypto/x509/platform_root_key.pem

pins=/usr/local/share/cursor-base/tools.lock
while read -r tool version _; do
    [[ -n "$tool" && "$tool" != \#* ]] || continue
    case "$tool" in
        go) have="$(GOTOOLCHAIN=local go version | awk '{sub(/^go/,"",$3); print $3}')" ;;
        node) have="$(node --version)"; have="${have#v}" ;;
        fnm|uv|just|zizmor) have="$("$tool" --version | awk 'NR==1{print $2}')" ;;
        python)
            version="${version%+*}"
            python_version="$version"
            have="$("$(uv python find --managed-python --no-python-downloads "$version")" -c 'import platform; print(platform.python_version())')"
            ;;
        gh) have="$(gh --version | awk 'NR==1{print $3}')" ;;
        actionlint) have="$(actionlint -version | awk 'NR==1{print $1}')" ;;
        docker-ce|docker-ce-cli|containerd.io|docker-buildx-plugin|docker-compose-plugin)
            installed="$(dpkg-query -W -f='${Version}' "$tool")"
            assert_equal "$tool deb" "$version~ubuntu.24.04~noble" "${installed#*:}"
            version="${version%-*}"
            case "$tool" in
                docker-ce) have="$(dockerd --version | awk '{sub(/,$/,"",$3); print $3}')" ;;
                docker-ce-cli) have="$(docker --version | awk '{sub(/,$/,"",$3); print $3}')" ;;
                containerd.io) have="$(containerd --version | awk '{sub(/^v/,"",$3); print $3}')" ;;
                docker-buildx-plugin) have="$(docker buildx version | awk '{sub(/^v/,"",$2); print $2}')" ;;
                docker-compose-plugin) have="$(docker compose version --short)"; have="${have#v}" ;;
            esac
            ;;
        *) printf 'Unknown pinned tool: %s\n' "$tool" >&2; exit 1 ;;
    esac
    assert_equal "$tool" "$version" "$have"
done < "$pins"

git --version
jq --version
shellcheck --version
python3 --version
npm --version
uvx --version
fuse-overlayfs --version
iptables --version | grep '(legacy)'
ip6tables --version | grep '(legacy)'
sudo -n dockerd --validate --config-file=/etc/docker/daemon.json
printf '%s\n' 'services:' '  smoke:' '    image: scratch' | docker compose -f - config --quiet

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"
python3 -m venv venv
test -w "$HOME/.local/share/uv/python"
uv venv --quiet --managed-python --no-python-downloads --python "$python_version" uv-venv
assert_equal 'Python in a uv environment' "$python_version" \
    "$(uv-venv/bin/python -c 'import platform; print(platform.python_version())')"
node_version="$(awk '$1=="node"{print $2}' "$pins")"
printf '%s\n' "$node_version" > .node-version
(
    eval "$(fnm env --shell bash)"
    fnm use </dev/null
    assert_equal 'Node selected from .node-version' "v$node_version" "$(node --version)"
)
assert_equal 'Node selected in a fresh shell' "v$node_version" \
    "$(fnm exec --using=.node-version -- node --version)"
printf '%s\n' 'int main(void) { return 0; }' > smoke.c
cc -static -o smoke smoke.c
./smoke

# A privileged, isolated outer container is required for this optional test.
# The inner build and container use no registry, host socket or network.
if [[ "$mode" == --docker ]]; then
    sudo -n service docker start
    timeout 30 bash -c 'until docker info --format "{{.Driver}}" 2>/dev/null; do sleep 1; done' > driver
    assert_equal docker-driver fuse-overlayfs "$(cat driver)"
    printf '%s\n' 'FROM scratch' 'COPY smoke /smoke' 'CMD ["/smoke"]' > Dockerfile
    docker build --network none --tag cursor-base-daemon-smoke .
    docker run --rm --network none cursor-base-daemon-smoke
fi
