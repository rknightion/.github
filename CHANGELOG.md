# Changelog

## [1.9.1](https://github.com/rknightion/.github/compare/v1.9.0...v1.9.1) (2026-08-19)


### Build & CI

* **deps:** update docker/setup-buildx-action action to v4.3.0 ([#55](https://github.com/rknightion/.github/issues/55)) ([4077d2c](https://github.com/rknightion/.github/commit/4077d2c3972c68a482b5487834933a69b7cb24cc))

## [1.9.0](https://github.com/rknightion/.github/compare/v1.8.0...v1.9.0) (2026-08-18)


### Features

* **arm-automerge:** make the runner configurable ([27fba8b](https://github.com/rknightion/.github/commit/27fba8b9f16ea23466fcfea158640f28812ce9b3))

## [1.8.0](https://github.com/rknightion/.github/compare/v1.7.0...v1.8.0) (2026-08-18)


### Features

* **arm-automerge:** add require-label so a repo can release fully automatically ([d79a0c5](https://github.com/rknightion/.github/commit/d79a0c5cef46dfddc24d8d698d4fc4076d9f600c))


### Bug Fixes

* **auto-rc:** warn instead of failing when CI is red ([e32ee05](https://github.com/rknightion/.github/commit/e32ee05fba532ff43a6e99f17b3da1b516305c8b))
* **ghcr-cleanup:** raise the job timeout for a first-time prune ([3795c83](https://github.com/rknightion/.github/commit/3795c834a504255b1788477755fb56b1479717b7))
* **sweep:** report the last STABLE release, not the newest prerelease ([1f56d2e](https://github.com/rknightion/.github/commit/1f56d2ec709b71dd33799130e4f8807579170b38))


### Build & CI

* use our own arm-automerge reusable on this repo's release PRs ([117b069](https://github.com/rknightion/.github/commit/117b069953f8441569a558430fb6311b0962bd44))


### Miscellaneous

* **tracker:** add GHC-0002 for the release automation work ([35e7db7](https://github.com/rknightion/.github/commit/35e7db7ab55e014fe9c72747391b2d5bfe0d0414))
* **tracker:** record the rollout inventory and the defects it surfaced ([89acacb](https://github.com/rknightion/.github/commit/89acacbc1a7c902d84cb3a81b71ed78c7beefb4c))

## [1.7.0](https://github.com/rknightion/.github/compare/v1.6.1...v1.7.0) (2026-08-18)


### Features

* **workflows:** add auto-rc reusable for automatic release candidates ([0043ba4](https://github.com/rknightion/.github/commit/0043ba42217751d3e403485d438bf90320dead1e))
* **workflows:** add auto-RC support workflows and fleet release sweep ([b340c7f](https://github.com/rknightion/.github/commit/b340c7f496648601087e8b56268c172f558b7054))


### Bug Fixes

* **auto-rc:** gh api rejects --slurp together with --jq ([abfb917](https://github.com/rknightion/.github/commit/abfb917ddc93841112e3b4cc3c90da0be0dd148f))
* **auto-rc:** treat a cancelled CI run as superseded, not failed ([3c70eb5](https://github.com/rknightion/.github/commit/3c70eb5f85aa5c288c23967533aeb23b32ab9607))
* **ghcr-cleanup:** flatten the protected-tags regex ([a363b59](https://github.com/rknightion/.github/commit/a363b594a7adc19292361081969f2d7af12026f7))
* **ghcr-cleanup:** stop the edge rule deleting stable releases ([2fa138d](https://github.com/rknightion/.github/commit/2fa138dfc8fa582001eaccb2b4f708ae463d9d0b))


### Refactor

* **actions:** make next-rc-tag a composite action ([f7accf3](https://github.com/rknightion/.github/commit/f7accf32f4a97ef424230d3e32ad626077bc4af8))


### Build & CI

* **deps:** update github/codeql-action action to v4.37.7 ([#48](https://github.com/rknightion/.github/issues/48)) ([f75c257](https://github.com/rknightion/.github/commit/f75c257695aee3e83ecc9bbf94bcdf2117cf307b))
* **deps:** update step-security/harden-runner action to v2.21.0 ([#50](https://github.com/rknightion/.github/issues/50)) ([1d56dc9](https://github.com/rknightion/.github/commit/1d56dc9ac43a302da02cbfeb714631b99f0f77e7))


### Documentation

* document the four new release-automation workflows ([5095ea2](https://github.com/rknightion/.github/commit/5095ea299501253ccbd528ff4f1967d0e8136fac))
* re-import fan-out protocol (context-cost rules) ([b7deade](https://github.com/rknightion/.github/commit/b7deadeda2bf1b33a6c2ecc63964d2ff8b70a4e9))
* **tracker:** align canonical fan-out protocol ([fda5f3b](https://github.com/rknightion/.github/commit/fda5f3b9a3f88f187a827e85b33181ea5668478e))


### Miscellaneous

* migrate issue tracking to Backlog.md, archive closed issues ([d207874](https://github.com/rknightion/.github/commit/d207874ba8d15fed9d9ec3c11b7957139e1a293d))

## [1.6.1](https://github.com/rknightion/.github/compare/v1.6.0...v1.6.1) (2026-08-12)


### Bug Fixes

* **ci:** verify actionlint downloads ([328bc72](https://github.com/rknightion/.github/commit/328bc72e11165b582079d424fd6b551221435250)), closes [#46](https://github.com/rknightion/.github/issues/46)

## [1.6.0](https://github.com/rknightion/.github/compare/v1.5.1...v1.6.0) (2026-08-08)


### Features

* add bao-secret action for generic KV reads ([7f9080f](https://github.com/rknightion/.github/commit/7f9080f3b84a1bbbbee25f6c8e6143b12e22dd94))
* add broker-token composite action ([468cc01](https://github.com/rknightion/.github/commit/468cc0199b5e49cf854c719495f9e1828d9a7ff3))
* allow skipping the tailnet join for already-joined runners ([5c1bdf7](https://github.com/rknightion/.github/commit/5c1bdf7f2fb1456d4cb0089de1089b803135e940))
* **broker-token:** support runners already on the tailnet ([f55d65c](https://github.com/rknightion/.github/commit/f55d65c2f96358b49d871ea5515c48fa3bce1fef))
* mint release-please token from the OpenBao broker ([0da8f49](https://github.com/rknightion/.github/commit/0da8f49263d4a6ccd1d1e2f8c8fe48fae0fc62a4))
* reach OpenBao via curl --resolve, and support in-cluster egress ([0104f58](https://github.com/rknightion/.github/commit/0104f5892b5ad5414c98bfdc213430dce083ad80))


### Bug Fixes

* allow the JWT role to differ from the permission set ([d43f0d6](https://github.com/rknightion/.github/commit/d43f0d6140bee0438725500c8977a340d0f0407f))
* **bao-secret:** stop ::add-mask:: leaking multi-line secrets to the log ([ea66f8e](https://github.com/rknightion/.github/commit/ea66f8eac8f05d697f087337c2311bd484757e70))
* **bao:** make a secret leak structurally impossible, not merely avoided ([06d6727](https://github.com/rknightion/.github/commit/06d6727487515cd6628e01696af6f886f1421e04))
* **bao:** stop using curl --fail-with-body, it is not portable ([b57e328](https://github.com/rknightion/.github/commit/b57e328fd53127925b32501d2c48b42630b2e07d))
* keep the runner's own resolver when joining the tailnet ([b9ab5f8](https://github.com/rknightion/.github/commit/b9ab5f80961f2c29c47a8d7d5dff112b6551169c))


### Build & CI

* **deps:** update actions/attest-build-provenance action to v4.2.2 ([#45](https://github.com/rknightion/.github/issues/45)) ([9d6bb9b](https://github.com/rknightion/.github/commit/9d6bb9b47c0cd7108d9fe0b874935bccd436f442))
* **deps:** update github/codeql-action action to v4.37.4 ([#38](https://github.com/rknightion/.github/issues/38)) ([af12a75](https://github.com/rknightion/.github/commit/af12a754b33e6f35a63faf7fae414fb62a09d814))
* **deps:** update github/codeql-action action to v4.37.5 ([#42](https://github.com/rknightion/.github/issues/42)) ([dd11e93](https://github.com/rknightion/.github/commit/dd11e933a585d0fc665aca22ea06b488fe8bb1f2))
* **deps:** update github/codeql-action action to v4.37.6 ([#43](https://github.com/rknightion/.github/issues/43)) ([9d4fc3a](https://github.com/rknightion/.github/commit/9d4fc3a2978b42eca18b9259a85dba3ff7cdb773))
* **deps:** update hadolint/hadolint-action action to v3.4.0 ([#40](https://github.com/rknightion/.github/issues/40)) ([64a3fed](https://github.com/rknightion/.github/commit/64a3fed6716e354ab2a311f136fc703109cf762b))
* **deps:** update step-security/harden-runner action to v2.20.1 ([#44](https://github.com/rknightion/.github/issues/44)) ([3df41d9](https://github.com/rknightion/.github/commit/3df41d927efc36b1637ed5e8d303d5c61b1f2041))
* **deps:** update zizmorcore/zizmor-action action to v0.6.2 ([#41](https://github.com/rknightion/.github/issues/41)) ([2cef6f9](https://github.com/rknightion/.github/commit/2cef6f9a8c98b228dad17ea3c9abd0dea78a3f36))


### Documentation

* correct the permission-set input description ([1cd0af4](https://github.com/rknightion/.github/commit/1cd0af4cdb0f46266b34f3b981543e32e7c98b4a))

## [1.5.1](https://github.com/rknightion/.github/compare/v1.5.0...v1.5.1) (2026-07-30)


### Build & CI

* **deps:** update dependency goreleaser/goreleaser to v2.17.1 ([#35](https://github.com/rknightion/.github/issues/35)) ([97aae72](https://github.com/rknightion/.github/commit/97aae722476d1cef638f1dadc5138b0fb2c6a856))
* **deps:** update docker/login-action action to v4.5.1 ([#33](https://github.com/rknightion/.github/issues/33)) ([753677b](https://github.com/rknightion/.github/commit/753677b09b35686a8caeea43e0d465269af382d1))
* **deps:** update docker/login-action action to v4.5.2 ([#36](https://github.com/rknightion/.github/issues/36)) ([90112ed](https://github.com/rknightion/.github/commit/90112edce5f2e6d5c4fdd829c6976a1411f847e1))
* **deps:** update docker/login-action action to v4.6.0 ([#37](https://github.com/rknightion/.github/issues/37)) ([aaf5b05](https://github.com/rknightion/.github/commit/aaf5b05211e740a14dbd09654326b63ca0151547))

## [1.5.0](https://github.com/rknightion/.github/compare/v1.4.3...v1.5.0) (2026-07-24)


### Features

* **binaries:** attest SLSA build provenance and attach it to the release ([7aa955c](https://github.com/rknightion/.github/commit/7aa955ca8134be9eac7bbd009317f35d6216bef5))


### Bug Fixes

* **binaries:** don't hand the attest step a cosign signature bundle ([d1c590b](https://github.com/rknightion/.github/commit/d1c590b295b9d7f2535fadc7bc5e74f2eddbd512))
* **container-publish:** keep the main chart version valid for every commit SHA ([3b135db](https://github.com/rknightion/.github/commit/3b135db545112f769452d13b8e2e4a3188d039de)), closes [#32](https://github.com/rknightion/.github/issues/32)


### Build & CI

* **deps:** update actions/checkout action to v7.0.1 ([#26](https://github.com/rknightion/.github/issues/26)) ([91fdca5](https://github.com/rknightion/.github/commit/91fdca5f9f7ec370807c2cd7f0d914623fa6c0d1))
* **deps:** update actions/setup-go action to v7 ([#24](https://github.com/rknightion/.github/issues/24)) ([a1949e4](https://github.com/rknightion/.github/commit/a1949e42e5d09687c429cc23b130dec20db91645))
* **deps:** update docker/login-action action to v4.5.0 ([#29](https://github.com/rknightion/.github/issues/29)) ([0c46bc4](https://github.com/rknightion/.github/commit/0c46bc4352a58ff4a607ed82c33525ba15731245))
* **deps:** update github/codeql-action action to v4.37.0 ([#22](https://github.com/rknightion/.github/issues/22)) ([49927d2](https://github.com/rknightion/.github/commit/49927d22cf1d85babc79e8cdf1f5751c884e9213))
* **deps:** update github/codeql-action action to v4.37.1 ([#25](https://github.com/rknightion/.github/issues/25)) ([7cd15a6](https://github.com/rknightion/.github/commit/7cd15a685736425653baf9e4afc242afd7655bb6))
* **deps:** update github/codeql-action action to v4.37.2 ([#27](https://github.com/rknightion/.github/issues/27)) ([1c6fb0f](https://github.com/rknightion/.github/commit/1c6fb0f44b9bd6aad4647615072a67ef9c79c285))
* **deps:** update github/codeql-action action to v4.37.3 ([#28](https://github.com/rknightion/.github/issues/28)) ([bfed06b](https://github.com/rknightion/.github/commit/bfed06b1e5f6c9f0209f55b1474b71ba18048782))
* **deps:** update ossf/scorecard-action action to v2.4.4 ([#30](https://github.com/rknightion/.github/issues/30)) ([aff0ef6](https://github.com/rknightion/.github/commit/aff0ef69ce57f276035976bacd3e0ed7b5fb58aa))
* **deps:** update step-security/harden-runner action to v2.20.0 ([#20](https://github.com/rknightion/.github/issues/20)) ([a4e935f](https://github.com/rknightion/.github/commit/a4e935fa402f95d270b039acabf19d8ee843f1f9))
* **deps:** update zizmorcore/zizmor-action action to v0.6.0 ([#23](https://github.com/rknightion/.github/issues/23)) ([828d5ef](https://github.com/rknightion/.github/commit/828d5ef270500e44d2681c0a9164f43aed178bb7))
* **deps:** update zizmorcore/zizmor-action action to v0.6.1 ([#31](https://github.com/rknightion/.github/issues/31)) ([2a0565b](https://github.com/rknightion/.github/commit/2a0565b425a8779518d38006876153de5dcad20e))

## [1.4.3](https://github.com/rknightion/.github/compare/v1.4.2...v1.4.3) (2026-07-05)


### Build & CI

* **deps:** update dependency goreleaser/goreleaser to v2.17.0 ([#18](https://github.com/rknightion/.github/issues/18)) ([b17fbf3](https://github.com/rknightion/.github/commit/b17fbf3e97365fda331e93404f82cd051ec0b235))

## [1.4.2](https://github.com/rknightion/.github/compare/v1.4.1...v1.4.2) (2026-07-04)


### Build & CI

* **deps:** update docker/login-action action to v4.4.0 ([#16](https://github.com/rknightion/.github/issues/16)) ([eadda13](https://github.com/rknightion/.github/commit/eadda137ec5a015e700f716c31bc13948c0e69e3))

## [1.4.1](https://github.com/rknightion/.github/compare/v1.4.0...v1.4.1) (2026-07-03)


### Build & CI

* add ci-success aggregator gate for Renovate automerge ([4369add](https://github.com/rknightion/.github/commit/4369add7433869dd464e5de7c331cdbc07a1298c)), closes [#13](https://github.com/rknightion/.github/issues/13)
* **release-please:** un-hide chore so action bumps land in releases ([d365eee](https://github.com/rknightion/.github/commit/d365eee8bf725c6d302f0286612d06dc2c86de6a)), closes [#15](https://github.com/rknightion/.github/issues/15)
* **renovate:** release action bumps by committing them as build(deps) ([de5c667](https://github.com/rknightion/.github/commit/de5c6676440deae4430bd642b3a5df97f66cc7b5)), closes [#14](https://github.com/rknightion/.github/issues/14)
* run OpenSSF Scorecard on the hub repo too ([20bd0fa](https://github.com/rknightion/.github/commit/20bd0fadd295bf16e471a0144e887fb1bfc0460e))


### Miscellaneous

* **deps:** update docker/build-push-action action to v7.3.0 ([#8](https://github.com/rknightion/.github/issues/8)) ([53b9678](https://github.com/rknightion/.github/commit/53b96783f4e0ff4d67e85595e4f2a11a8be59e8e))
* **deps:** update docker/login-action action to v4.3.0 ([#9](https://github.com/rknightion/.github/issues/9)) ([d478792](https://github.com/rknightion/.github/commit/d4787920047bab8c27d878658418c016c4d0ed61))
* **deps:** update docker/metadata-action action to v6.2.0 ([#10](https://github.com/rknightion/.github/issues/10)) ([3592bb4](https://github.com/rknightion/.github/commit/3592bb41d28f5a4e40ed64dfa324ea594747e69f))
* **deps:** update docker/setup-buildx-action action to v4.2.0 ([#11](https://github.com/rknightion/.github/issues/11)) ([841c285](https://github.com/rknightion/.github/commit/841c28582efe2b6c0715d138608a3ddd5014fd2c))
* **deps:** update github/codeql-action action to v4.36.3 ([#7](https://github.com/rknightion/.github/issues/7)) ([381d47c](https://github.com/rknightion/.github/commit/381d47cb476ac56b6f5992fb346fdf961cdc00b8))

## [1.4.0](https://github.com/rknightion/.github/compare/v1.3.1...v1.4.0) (2026-07-03)


### Features

* add reusable OpenSSF Scorecard workflow ([8537db9](https://github.com/rknightion/.github/commit/8537db9ace5d83b3cf0f6b4c75f0cf2e72450c1a))


### Build & CI

* remove notify-maintainer-on-new-issue workflow ([0202d96](https://github.com/rknightion/.github/commit/0202d96e978bd709c594b1aa2ea1ca174e86ee0b))
* **renovate:** add canonical shared preset, treat Action SHAs as immutable ([7201765](https://github.com/rknightion/.github/commit/720176561c4eb865fb7a8609b33aee1471deb2e5))
* **renovate:** consolidate on self-hosted config.js, drop redundant preset ([01f9654](https://github.com/rknightion/.github/commit/01f9654e966f58996174b9a96277d216efb4750b))
* **renovate:** slim repo config to GoReleaser tracker only ([d8904fb](https://github.com/rknightion/.github/commit/d8904fb499e427e2e1154412c099768d94ea0440))

## [1.3.1](https://github.com/rknightion/.github/compare/v1.3.0...v1.3.1) (2026-06-29)


### Bug Fixes

* **container-publish:** set GH_REPO on release-asset uploads ([4284c03](https://github.com/rknightion/.github/commit/4284c03e49b249f11bfc700ce0a4eded1fa7997a))

## [1.3.0](https://github.com/rknightion/.github/compare/v1.2.0...v1.3.0) (2026-06-29)


### Features

* concurrency + job timeouts across all reusables ([a4c8662](https://github.com/rknightion/.github/commit/a4c8662649e4c3723d561f826736b8436a72c515))


### Bug Fixes

* **ci:** grant actions:read to the zizmor self-CI job ([f6daced](https://github.com/rknightion/.github/commit/f6daced16b779bc40d44a62274d07dc9b8c843fd))


### Build & CI

* dogfood CodeQL actions analysis; Renovate-track the GoReleaser CLI version ([67fa076](https://github.com/rknightion/.github/commit/67fa0766e589ce971df597ad1c3692b20f723c1c))
