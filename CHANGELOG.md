# Changelog

## [1.18.2](https://github.com/rknightion/.github/compare/v1.18.1...v1.18.2) (2026-09-02)


### Bug Fixes

* **codeql:** restore codeql-config.yml consumed by pinned callers ([09c52f4](https://github.com/rknightion/.github/commit/09c52f4a93141d95a4d5b1420d438861fe5640bb))

## [1.18.1](https://github.com/rknightion/.github/compare/v1.18.0...v1.18.1) (2026-09-01)


### Bug Fixes

* **container-publish:** scan OCI layouts before push ([e17ff96](https://github.com/rknightion/.github/commit/e17ff969ee2273736a4d9dfc0e0d073a9a93848c))

## [1.18.0](https://github.com/rknightion/.github/compare/v1.17.1...v1.18.0) (2026-09-01)


### Features

* **ci:** gate publication on security severity (MDE-0003) ([240da9e](https://github.com/rknightion/.github/commit/240da9e373020bf3bed9264c5bead071e56d79aa))

## [1.17.1](https://github.com/rknightion/.github/compare/v1.17.0...v1.17.1) (2026-08-29)


### Documentation

* **ci:** document just task surface ([84e2fbc](https://github.com/rknightion/.github/commit/84e2fbcd8a169602e994596f8f94c7f9d887207e))

## [1.17.0](https://github.com/rknightion/.github/compare/v1.16.0...v1.17.0) (2026-08-29)


### Features

* add bao-secret action for generic KV reads ([7f9080f](https://github.com/rknightion/.github/commit/7f9080f3b84a1bbbbee25f6c8e6143b12e22dd94))
* add binaries reusable; self-CI, release-please + Renovate automation ([9eaba49](https://github.com/rknightion/.github/commit/9eaba495bc5f41c780ea4508e52ea1a20330c04f))
* add broker-token composite action ([468cc01](https://github.com/rknightion/.github/commit/468cc0199b5e49cf854c719495f9e1828d9a7ff3))
* add reusable OpenSSF Scorecard workflow ([8537db9](https://github.com/rknightion/.github/commit/8537db9ace5d83b3cf0f6b4c75f0cf2e72450c1a))
* allow skipping the tailnet join for already-joined runners ([5c1bdf7](https://github.com/rknightion/.github/commit/5c1bdf7f2fb1456d4cb0089de1089b803135e940))
* **arm-automerge:** add require-label so a repo can release fully automatically ([d79a0c5](https://github.com/rknightion/.github/commit/d79a0c5cef46dfddc24d8d698d4fc4076d9f600c))
* **arm-automerge:** make the runner configurable ([27fba8b](https://github.com/rknightion/.github/commit/27fba8b9f16ea23466fcfea158640f28812ce9b3))
* **auto-rc:** add sha input so callers can trigger on workflow_run ([ec685e0](https://github.com/rknightion/.github/commit/ec685e063babbaed1917883cfa8dd7f0a88d8533))
* **binaries:** attest SLSA build provenance and attach it to the release ([7aa955c](https://github.com/rknightion/.github/commit/7aa955ca8134be9eac7bbd009317f35d6216bef5))
* **broker-token:** support runners already on the tailnet ([f55d65c](https://github.com/rknightion/.github/commit/f55d65c2f96358b49d871ea5515c48fa3bce1fef))
* **ci:** add reusable just gate ([5c718d5](https://github.com/rknightion/.github/commit/5c718d59954bd0e97c4e04d57b3dd02b8c10d229))
* **ci:** add the just task surface ([4497319](https://github.com/rknightion/.github/commit/4497319d950b5cc0cc15aa5cc6566f9f38b5841d))
* concurrency + job timeouts across all reusables ([a4c8662](https://github.com/rknightion/.github/commit/a4c8662649e4c3723d561f826736b8436a72c515))
* **container-publish:** add reusable multi-arch publish workflow ([e2e1cd4](https://github.com/rknightion/.github/commit/e2e1cd419b9e2f8c6185af99c8cb40c25ae9c412))
* **container-publish:** auto-inject VERSION build-arg (stripped tag / short sha) ([34562c9](https://github.com/rknightion/.github/commit/34562c9509ba239a593a27a7f2be25f5398ab550))
* **container-publish:** opt-in BuildKit OTEL build tracing ([eb29aab](https://github.com/rknightion/.github/commit/eb29aabc2233e17587a36d6883f59e3d2d0d6464))
* **container-publish:** time-sortable main snapshot chart version (ArgoCD) ([132d8a6](https://github.com/rknightion/.github/commit/132d8a61d5d2fcf8e0932cb9f56376ad1dbf54af))
* **fleet:** audit public repo settings and report drift ([9a79bbc](https://github.com/rknightion/.github/commit/9a79bbcb07aeb9e3d43b206e102801eed9f781ea))
* **fleet:** enable the weekly settings drift cron ([397938b](https://github.com/rknightion/.github/commit/397938b6e6fbf78ca4a888fc2034c988d3923d29))
* **fleet:** switch on the weekly repo-settings drift report ([908b3d6](https://github.com/rknightion/.github/commit/908b3d6d7937b437db5f835836cb5c85f7c3a8ee))
* **ghcr-cleanup:** add runs-on and harden inputs for self-hosted callers ([9dd6053](https://github.com/rknightion/.github/commit/9dd6053b99d7d52d042f96acb1c7349ab9b9e817))
* **helm-validate:** add a shared chart lint + render + schema-validation reusable ([905df03](https://github.com/rknightion/.github/commit/905df031654bc6927eb8339c6035c3b340d141ec))
* mint release-please token from the OpenBao broker ([0da8f49](https://github.com/rknightion/.github/commit/0da8f49263d4a6ccd1d1e2f8c8fe48fae0fc62a4))
* reach OpenBao via curl --resolve, and support in-cluster egress ([0104f58](https://github.com/rknightion/.github/commit/0104f5892b5ad5414c98bfdc213430dce083ad80))
* **snyk:** add reusable Snyk -&gt; Snyk Cloud monitor workflow ([39131d6](https://github.com/rknightion/.github/commit/39131d6288b110fa422a92ca2315cb4e7bafde21))
* **workflows:** add auto-rc reusable for automatic release candidates ([0043ba4](https://github.com/rknightion/.github/commit/0043ba42217751d3e403485d438bf90320dead1e))
* **workflows:** add auto-RC support workflows and fleet release sweep ([b340c7f](https://github.com/rknightion/.github/commit/b340c7f496648601087e8b56268c172f558b7054))


### Bug Fixes

* **actions:** fail clearly on unresolved Bao host ([f2c547a](https://github.com/rknightion/.github/commit/f2c547ab3f199be26bd439664edaa16cd72450d1))
* allow the JWT role to differ from the permission set ([d43f0d6](https://github.com/rknightion/.github/commit/d43f0d6140bee0438725500c8977a340d0f0407f))
* **auto-rc:** gh api rejects --slurp together with --jq ([abfb917](https://github.com/rknightion/.github/commit/abfb917ddc93841112e3b4cc3c90da0be0dd148f))
* **auto-rc:** treat a cancelled CI run as superseded, not failed ([3c70eb5](https://github.com/rknightion/.github/commit/3c70eb5f85aa5c288c23967533aeb23b32ab9607))
* **auto-rc:** warn instead of failing when CI is red ([e32ee05](https://github.com/rknightion/.github/commit/e32ee05fba532ff43a6e99f17b3da1b516305c8b))
* **bao-secret:** stop ::add-mask:: leaking multi-line secrets to the log ([ea66f8e](https://github.com/rknightion/.github/commit/ea66f8eac8f05d697f087337c2311bd484757e70))
* **bao:** make a secret leak structurally impossible, not merely avoided ([06d6727](https://github.com/rknightion/.github/commit/06d6727487515cd6628e01696af6f886f1421e04))
* **bao:** stop using curl --fail-with-body, it is not portable ([b57e328](https://github.com/rknightion/.github/commit/b57e328fd53127925b32501d2c48b42630b2e07d))
* **binaries:** don't hand the attest step a cosign signature bundle ([d1c590b](https://github.com/rknightion/.github/commit/d1c590b295b9d7f2535fadc7bc5e74f2eddbd512))
* **ci:** grant actions:read to the zizmor self-CI job ([f6daced](https://github.com/rknightion/.github/commit/f6daced16b779bc40d44a62274d07dc9b8c843fd))
* **ci:** verify actionlint downloads ([328bc72](https://github.com/rknightion/.github/commit/328bc72e11165b582079d424fd6b551221435250)), closes [#46](https://github.com/rknightion/.github/issues/46)
* **container-publish:** docker login in helm job so cosign can push chart signature ([87b35bf](https://github.com/rknightion/.github/commit/87b35bfaa5695ede899f7c6c2472e683ee8d4567))
* **container-publish:** keep the main chart version valid for every commit SHA ([3b135db](https://github.com/rknightion/.github/commit/3b135db545112f769452d13b8e2e4a3188d039de)), closes [#32](https://github.com/rknightion/.github/issues/32)
* **container-publish:** set GH_REPO on release-asset uploads ([4284c03](https://github.com/rknightion/.github/commit/4284c03e49b249f11bfc700ce0a4eded1fa7997a))
* **fleet:** grant id-token: write so the broker can mint ([1ddef41](https://github.com/rknightion/.github/commit/1ddef41375c4ee91624c4435f41cc2ebbb813580))
* **fleet:** park the drift cron until the App holds administration ([560656e](https://github.com/rknightion/.github/commit/560656ee53d475d7d4e7f096e13567600871e802))
* **fleet:** pass Tailscale identity to the broker on a hosted runner ([0772de6](https://github.com/rknightion/.github/commit/0772de69029b54445a9549142148e0f46c4f2bd8))
* **ghcr-cleanup:** flatten the protected-tags regex ([a363b59](https://github.com/rknightion/.github/commit/a363b594a7adc19292361081969f2d7af12026f7))
* **ghcr-cleanup:** raise the job timeout for a first-time prune ([3795c83](https://github.com/rknightion/.github/commit/3795c834a504255b1788477755fb56b1479717b7))
* **ghcr-cleanup:** stop the edge rule deleting stable releases ([2fa138d](https://github.com/rknightion/.github/commit/2fa138dfc8fa582001eaccb2b4f708ae463d9d0b))
* **helm-validate:** stop a trailing newline requesting a default render ([01bcffa](https://github.com/rknightion/.github/commit/01bcffad655a738a90399fdb8de2064cf37dd00c))
* keep the runner's own resolver when joining the tailnet ([b9ab5f8](https://github.com/rknightion/.github/commit/b9ab5f80961f2c29c47a8d7d5dff112b6551169c))
* **sweep:** report the last STABLE release, not the newest prerelease ([1f56d2e](https://github.com/rknightion/.github/commit/1f56d2ec709b71dd33799130e4f8807579170b38))


### Refactor

* **actions:** make next-rc-tag a composite action ([f7accf3](https://github.com/rknightion/.github/commit/f7accf32f4a97ef424230d3e32ad626077bc4af8))


### Build & CI

* add ci-success aggregator gate for Renovate automerge ([4369add](https://github.com/rknightion/.github/commit/4369add7433869dd464e5de7c331cdbc07a1298c)), closes [#13](https://github.com/rknightion/.github/issues/13)
* auto-assign maintainer on new issues (notify by email) ([db51115](https://github.com/rknightion/.github/commit/db51115b370bef0ad53825ba60d18675b2514490))
* bump the broker-token action pin ([d97ef42](https://github.com/rknightion/.github/commit/d97ef42f9c9649a34137870d05fae8cb206d8fc0))
* **deps:** update actions/attest-build-provenance action to v4.2.2 ([#45](https://github.com/rknightion/.github/issues/45)) ([9d6bb9b](https://github.com/rknightion/.github/commit/9d6bb9b47c0cd7108d9fe0b874935bccd436f442))
* **deps:** update actions/checkout action to v7.0.1 ([#26](https://github.com/rknightion/.github/issues/26)) ([91fdca5](https://github.com/rknightion/.github/commit/91fdca5f9f7ec370807c2cd7f0d914623fa6c0d1))
* **deps:** update actions/setup-go action to v7 ([#24](https://github.com/rknightion/.github/issues/24)) ([a1949e4](https://github.com/rknightion/.github/commit/a1949e42e5d09687c429cc23b130dec20db91645))
* **deps:** update actions/upload-artifact action to v7 ([#78](https://github.com/rknightion/.github/issues/78)) ([df98e2a](https://github.com/rknightion/.github/commit/df98e2a76d1e34e94e0f28e9583832c1536488f2))
* **deps:** update anchore/sbom-action action to v0.24.1 ([#67](https://github.com/rknightion/.github/issues/67)) ([edf55fa](https://github.com/rknightion/.github/commit/edf55fa2f7ec23844253c618ad7136780143bbde))
* **deps:** update anchore/sbom-action action to v0.24.2 ([#70](https://github.com/rknightion/.github/issues/70)) ([5ab9bc0](https://github.com/rknightion/.github/commit/5ab9bc001bc6c4dd397a02e56711c5689bd66a0f))
* **deps:** update dependency goreleaser/goreleaser to v2.17.0 ([#18](https://github.com/rknightion/.github/issues/18)) ([b17fbf3](https://github.com/rknightion/.github/commit/b17fbf3e97365fda331e93404f82cd051ec0b235))
* **deps:** update dependency goreleaser/goreleaser to v2.17.1 ([#35](https://github.com/rknightion/.github/issues/35)) ([97aae72](https://github.com/rknightion/.github/commit/97aae722476d1cef638f1dadc5138b0fb2c6a856))
* **deps:** update dependency goreleaser/goreleaser to v2.18.0 ([#60](https://github.com/rknightion/.github/issues/60)) ([d998d32](https://github.com/rknightion/.github/commit/d998d32c78aeb3e0ec0b434bec910b147136418d))
* **deps:** update docker/login-action action to v4.4.0 ([#16](https://github.com/rknightion/.github/issues/16)) ([eadda13](https://github.com/rknightion/.github/commit/eadda137ec5a015e700f716c31bc13948c0e69e3))
* **deps:** update docker/login-action action to v4.5.0 ([#29](https://github.com/rknightion/.github/issues/29)) ([0c46bc4](https://github.com/rknightion/.github/commit/0c46bc4352a58ff4a607ed82c33525ba15731245))
* **deps:** update docker/login-action action to v4.5.1 ([#33](https://github.com/rknightion/.github/issues/33)) ([753677b](https://github.com/rknightion/.github/commit/753677b09b35686a8caeea43e0d465269af382d1))
* **deps:** update docker/login-action action to v4.5.2 ([#36](https://github.com/rknightion/.github/issues/36)) ([90112ed](https://github.com/rknightion/.github/commit/90112edce5f2e6d5c4fdd829c6976a1411f847e1))
* **deps:** update docker/login-action action to v4.6.0 ([#37](https://github.com/rknightion/.github/issues/37)) ([aaf5b05](https://github.com/rknightion/.github/commit/aaf5b05211e740a14dbd09654326b63ca0151547))
* **deps:** update docker/setup-buildx-action action to v4.3.0 ([#55](https://github.com/rknightion/.github/issues/55)) ([4077d2c](https://github.com/rknightion/.github/commit/4077d2c3972c68a482b5487834933a69b7cb24cc))
* **deps:** update github/codeql-action action to v4.37.0 ([#22](https://github.com/rknightion/.github/issues/22)) ([49927d2](https://github.com/rknightion/.github/commit/49927d22cf1d85babc79e8cdf1f5751c884e9213))
* **deps:** update github/codeql-action action to v4.37.1 ([#25](https://github.com/rknightion/.github/issues/25)) ([7cd15a6](https://github.com/rknightion/.github/commit/7cd15a685736425653baf9e4afc242afd7655bb6))
* **deps:** update github/codeql-action action to v4.37.2 ([#27](https://github.com/rknightion/.github/issues/27)) ([1c6fb0f](https://github.com/rknightion/.github/commit/1c6fb0f44b9bd6aad4647615072a67ef9c79c285))
* **deps:** update github/codeql-action action to v4.37.3 ([#28](https://github.com/rknightion/.github/issues/28)) ([bfed06b](https://github.com/rknightion/.github/commit/bfed06b1e5f6c9f0209f55b1474b71ba18048782))
* **deps:** update github/codeql-action action to v4.37.4 ([#38](https://github.com/rknightion/.github/issues/38)) ([af12a75](https://github.com/rknightion/.github/commit/af12a754b33e6f35a63faf7fae414fb62a09d814))
* **deps:** update github/codeql-action action to v4.37.5 ([#42](https://github.com/rknightion/.github/issues/42)) ([dd11e93](https://github.com/rknightion/.github/commit/dd11e933a585d0fc665aca22ea06b488fe8bb1f2))
* **deps:** update github/codeql-action action to v4.37.6 ([#43](https://github.com/rknightion/.github/issues/43)) ([9d4fc3a](https://github.com/rknightion/.github/commit/9d4fc3a2978b42eca18b9259a85dba3ff7cdb773))
* **deps:** update github/codeql-action action to v4.37.7 ([#48](https://github.com/rknightion/.github/issues/48)) ([f75c257](https://github.com/rknightion/.github/commit/f75c257695aee3e83ecc9bbf94bcdf2117cf307b))
* **deps:** update github/codeql-action action to v4.37.8 ([#57](https://github.com/rknightion/.github/issues/57)) ([3807359](https://github.com/rknightion/.github/commit/3807359bfb67ad88b8b3853ce19a6d4562060a5d))
* **deps:** update github/codeql-action action to v4.37.9 ([#65](https://github.com/rknightion/.github/issues/65)) ([ae38515](https://github.com/rknightion/.github/commit/ae385159ce6a835c58fff92b32387def65a49924))
* **deps:** update hadolint/hadolint-action action to v3.4.0 ([#40](https://github.com/rknightion/.github/issues/40)) ([64a3fed](https://github.com/rknightion/.github/commit/64a3fed6716e354ab2a311f136fc703109cf762b))
* **deps:** update hadolint/hadolint-action action to v3.5.0 ([#63](https://github.com/rknightion/.github/issues/63)) ([b9f5d34](https://github.com/rknightion/.github/commit/b9f5d3461064bbdb12ea6e4cc9e7b51e9e868937))
* **deps:** update ossf/scorecard-action action to v2.4.4 ([#30](https://github.com/rknightion/.github/issues/30)) ([aff0ef6](https://github.com/rknightion/.github/commit/aff0ef69ce57f276035976bacd3e0ed7b5fb58aa))
* **deps:** update rknightion/.github action to v1.9.8 ([#73](https://github.com/rknightion/.github/issues/73)) ([8512368](https://github.com/rknightion/.github/commit/851236813e0534dfe9f24aca502e9cbc9f3d5be0))
* **deps:** update step-security/harden-runner action to v2.20.0 ([#20](https://github.com/rknightion/.github/issues/20)) ([a4e935f](https://github.com/rknightion/.github/commit/a4e935fa402f95d270b039acabf19d8ee843f1f9))
* **deps:** update step-security/harden-runner action to v2.20.1 ([#44](https://github.com/rknightion/.github/issues/44)) ([3df41d9](https://github.com/rknightion/.github/commit/3df41d927efc36b1637ed5e8d303d5c61b1f2041))
* **deps:** update step-security/harden-runner action to v2.21.0 ([#50](https://github.com/rknightion/.github/issues/50)) ([1d56dc9](https://github.com/rknightion/.github/commit/1d56dc9ac43a302da02cbfeb714631b99f0f77e7))
* **deps:** update zizmorcore/zizmor-action action to v0.6.0 ([#23](https://github.com/rknightion/.github/issues/23)) ([828d5ef](https://github.com/rknightion/.github/commit/828d5ef270500e44d2681c0a9164f43aed178bb7))
* **deps:** update zizmorcore/zizmor-action action to v0.6.1 ([#31](https://github.com/rknightion/.github/issues/31)) ([2a0565b](https://github.com/rknightion/.github/commit/2a0565b425a8779518d38006876153de5dcad20e))
* **deps:** update zizmorcore/zizmor-action action to v0.6.2 ([#41](https://github.com/rknightion/.github/issues/41)) ([2cef6f9](https://github.com/rknightion/.github/commit/2cef6f9a8c98b228dad17ea3c9abd0dea78a3f36))
* dogfood CodeQL actions analysis; Renovate-track the GoReleaser CLI version ([67fa076](https://github.com/rknightion/.github/commit/67fa0766e589ce971df597ad1c3692b20f723c1c))
* enforce just check in self-ci ([2e18e12](https://github.com/rknightion/.github/commit/2e18e12d53516fb0480894f1f5af65ded9108627))
* harden reusable workflows for fork PRs + first-party [@main](https://github.com/main) pin policy ([17626c1](https://github.com/rknightion/.github/commit/17626c13325fb83a09c6ace6db2d280d83bbd494))
* **release-please:** un-hide chore so action bumps land in releases ([d365eee](https://github.com/rknightion/.github/commit/d365eee8bf725c6d302f0286612d06dc2c86de6a)), closes [#15](https://github.com/rknightion/.github/issues/15)
* remove notify-maintainer-on-new-issue workflow ([0202d96](https://github.com/rknightion/.github/commit/0202d96e978bd709c594b1aa2ea1ca174e86ee0b))
* **renovate:** add canonical shared preset, treat Action SHAs as immutable ([7201765](https://github.com/rknightion/.github/commit/720176561c4eb865fb7a8609b33aee1471deb2e5))
* **renovate:** consolidate on self-hosted config.js, drop redundant preset ([01f9654](https://github.com/rknightion/.github/commit/01f9654e966f58996174b9a96277d216efb4750b))
* **renovate:** release action bumps by committing them as build(deps) ([de5c667](https://github.com/rknightion/.github/commit/de5c6676440deae4430bd642b3a5df97f66cc7b5)), closes [#14](https://github.com/rknightion/.github/issues/14)
* **renovate:** slim repo config to GoReleaser tracker only ([d8904fb](https://github.com/rknightion/.github/commit/d8904fb499e427e2e1154412c099768d94ea0440))
* run OpenSSF Scorecard on the hub repo too ([20bd0fa](https://github.com/rknightion/.github/commit/20bd0fadd295bf16e471a0144e887fb1bfc0460e))
* use our own arm-automerge reusable on this repo's release PRs ([117b069](https://github.com/rknightion/.github/commit/117b069953f8441569a558430fb6311b0962bd44))
* **zizmor:** apply unpinned-uses policy via auto-discovered .github/zizmor.yml ([0e80ff5](https://github.com/rknightion/.github/commit/0e80ff55d8b0bf7910f6f7048388657e0571f495))
* **zizmor:** require hash-pin for all uses, including first-party reusables ([7a03d31](https://github.com/rknightion/.github/commit/7a03d3150778d4b39c75440eb244a7feb23239d6))


### Documentation

* correct the permission-set input description ([1cd0af4](https://github.com/rknightion/.github/commit/1cd0af4cdb0f46266b34f3b981543e32e7c98b4a))
* document the four new release-automation workflows ([5095ea2](https://github.com/rknightion/.github/commit/5095ea299501253ccbd528ff4f1967d0e8136fac))
* re-import fan-out protocol (context-cost rules) ([b7deade](https://github.com/rknightion/.github/commit/b7deadeda2bf1b33a6c2ecc63964d2ff8b70a4e9))
* **tracker:** align canonical fan-out protocol ([fda5f3b](https://github.com/rknightion/.github/commit/fda5f3b9a3f88f187a827e85b33181ea5668478e))


### Miscellaneous

* **backlog:** add GHC-0003 — migrate the repo task surface to just ([a38cc71](https://github.com/rknightion/.github/commit/a38cc71c2081a2893b0b95cf28666ad2a2c56e44))
* **backlog:** add GHC-0004 — harvest egress audits, then move to block mode ([0f93339](https://github.com/rknightion/.github/commit/0f93339c6927ae51c478587852b6a9f21acd1cf1))
* **backlog:** open the parent task for the fleet justfile campaign ([1ee377f](https://github.com/rknightion/.github/commit/1ee377f1d46911a2e8b6d50241c634461aec794d))
* **backlog:** ratify ci as the sanctioned superset of check ([2802e25](https://github.com/rknightion/.github/commit/2802e25ea6be027d934f463608e65f0b9e95d5db))
* **backlog:** wire the fleet migration ordering into this task ([ce2749f](https://github.com/rknightion/.github/commit/ce2749f15452f38f51bbfa71836b6927bb05336a))
* **deps:** update docker/build-push-action action to v7.3.0 ([#8](https://github.com/rknightion/.github/issues/8)) ([53b9678](https://github.com/rknightion/.github/commit/53b96783f4e0ff4d67e85595e4f2a11a8be59e8e))
* **deps:** update docker/login-action action to v4.3.0 ([#9](https://github.com/rknightion/.github/issues/9)) ([d478792](https://github.com/rknightion/.github/commit/d4787920047bab8c27d878658418c016c4d0ed61))
* **deps:** update docker/metadata-action action to v6.2.0 ([#10](https://github.com/rknightion/.github/issues/10)) ([3592bb4](https://github.com/rknightion/.github/commit/3592bb41d28f5a4e40ed64dfa324ea594747e69f))
* **deps:** update docker/setup-buildx-action action to v4.2.0 ([#11](https://github.com/rknightion/.github/issues/11)) ([841c285](https://github.com/rknightion/.github/commit/841c28582efe2b6c0715d138608a3ddd5014fd2c))
* **deps:** update github/codeql-action action to v4.36.3 ([#7](https://github.com/rknightion/.github/issues/7)) ([381d47c](https://github.com/rknightion/.github/commit/381d47cb476ac56b6f5992fb346fdf961cdc00b8))
* **fleet:** record the settings audit as clean ([98d6a92](https://github.com/rknightion/.github/commit/98d6a921f2018ead7b86ca4b3fbb1c50e4f6e818))
* **hooks:** retire the repo-local Backlog guard for the global one ([8e44ba3](https://github.com/rknightion/.github/commit/8e44ba3d6041a9644022e57b47fb55bff7dc539b))
* **main:** release 1.10.0 ([#74](https://github.com/rknightion/.github/issues/74)) ([b3f1cef](https://github.com/rknightion/.github/commit/b3f1cef6e76ce206b01e1a3bae63ce115a1cf570))
* **main:** release 1.10.1 ([#75](https://github.com/rknightion/.github/issues/75)) ([99a633c](https://github.com/rknightion/.github/commit/99a633c653561f10ef871cac2f3b2e3aad13bb5f))
* **main:** release 1.11.0 ([#76](https://github.com/rknightion/.github/issues/76)) ([8739625](https://github.com/rknightion/.github/commit/873962525bd50b84dfdb3226efab8c8e2cd6a9a2))
* **main:** release 1.12.0 ([#77](https://github.com/rknightion/.github/issues/77)) ([c4fb6a5](https://github.com/rknightion/.github/commit/c4fb6a565837068423a8cdaa6db07384c6f5dd61))
* **main:** release 1.13.0 ([#79](https://github.com/rknightion/.github/issues/79)) ([5a2b8d0](https://github.com/rknightion/.github/commit/5a2b8d059084a79d11c9675f2fd07abd7003f915))
* **main:** release 1.14.0 ([#80](https://github.com/rknightion/.github/issues/80)) ([97f4a7a](https://github.com/rknightion/.github/commit/97f4a7ad0cd1ddd83562a30b9061ef8295242405))
* **main:** release 1.15.0 ([#81](https://github.com/rknightion/.github/issues/81)) ([0e21ae9](https://github.com/rknightion/.github/commit/0e21ae9045ca3e5ae522b711030b70c53b8d94be))
* **main:** release 1.15.1 ([#82](https://github.com/rknightion/.github/issues/82)) ([1ee5634](https://github.com/rknightion/.github/commit/1ee56349bfcf2568e538479918b9bdd1b9196309))
* **main:** release 1.16.0 ([#83](https://github.com/rknightion/.github/issues/83)) ([b5bd8ef](https://github.com/rknightion/.github/commit/b5bd8ef5c790b302a784d09b2f5f449ff77a1886))
* **main:** release 1.3.0 ([#2](https://github.com/rknightion/.github/issues/2)) ([d86fed4](https://github.com/rknightion/.github/commit/d86fed4bbd1ea0cc0009ea557dca9e63d2e088bd))
* **main:** release 1.3.1 ([#4](https://github.com/rknightion/.github/issues/4)) ([f316906](https://github.com/rknightion/.github/commit/f31690684f4292d1fe8e528618f7c8306fe27d9a))
* **main:** release 1.4.0 ([#5](https://github.com/rknightion/.github/issues/5)) ([8718898](https://github.com/rknightion/.github/commit/8718898e512efc196dba6888b7d20d7b21019bf2))
* **main:** release 1.4.1 ([#12](https://github.com/rknightion/.github/issues/12)) ([66ec45b](https://github.com/rknightion/.github/commit/66ec45b9243431ecb2a2585cc7bbd6d6af0398ff))
* **main:** release 1.4.2 ([#17](https://github.com/rknightion/.github/issues/17)) ([60bd1be](https://github.com/rknightion/.github/commit/60bd1bea8bb6c8cf45456e0daaf8c5ce4cb51b62))
* **main:** release 1.4.3 ([#19](https://github.com/rknightion/.github/issues/19)) ([65aedb6](https://github.com/rknightion/.github/commit/65aedb61754e9bf31e947c17409256ba0c58c637))
* **main:** release 1.5.0 ([#21](https://github.com/rknightion/.github/issues/21)) ([a4182f2](https://github.com/rknightion/.github/commit/a4182f2ed573c3b5015e195b797d1e96cf09a8bf))
* **main:** release 1.5.1 ([#34](https://github.com/rknightion/.github/issues/34)) ([0228d8b](https://github.com/rknightion/.github/commit/0228d8b9f1e36ff3a1d0906574d70fa174ddc7bf))
* **main:** release 1.6.0 ([#39](https://github.com/rknightion/.github/issues/39)) ([25bb335](https://github.com/rknightion/.github/commit/25bb3358282749dfb3d4f865579411253bc4beae))
* **main:** release 1.6.1 ([#47](https://github.com/rknightion/.github/issues/47)) ([09f7bac](https://github.com/rknightion/.github/commit/09f7bac7a5d4f59c031fffa8485ee376c9fedce0))
* **main:** release 1.7.0 ([#49](https://github.com/rknightion/.github/issues/49)) ([1e0f45b](https://github.com/rknightion/.github/commit/1e0f45bfdc28163f4e3ae99a7d497638ac6d9223))
* **main:** release 1.8.0 ([#53](https://github.com/rknightion/.github/issues/53)) ([08886c6](https://github.com/rknightion/.github/commit/08886c63bb10e8f23a2ce82a2ebbfce4d3ca932c))
* **main:** release 1.9.0 ([#54](https://github.com/rknightion/.github/issues/54)) ([a83125b](https://github.com/rknightion/.github/commit/a83125ba50572d13b55c5b4fb425dcb062f63eea))
* **main:** release 1.9.1 ([#56](https://github.com/rknightion/.github/issues/56)) ([3eccd1b](https://github.com/rknightion/.github/commit/3eccd1b2f86c998fde32790f370da41d10a4c89b))
* **main:** release 1.9.10 ([#71](https://github.com/rknightion/.github/issues/71)) ([9c3981d](https://github.com/rknightion/.github/commit/9c3981da69a2aa4eecd99e5740335219fd8c6a00))
* **main:** release 1.9.11 ([#72](https://github.com/rknightion/.github/issues/72)) ([30d4340](https://github.com/rknightion/.github/commit/30d43409fab7266a749ccf1a1c72ebcf79242d2c))
* **main:** release 1.9.2 ([#58](https://github.com/rknightion/.github/issues/58)) ([2616861](https://github.com/rknightion/.github/commit/26168618790b1fec60c02677343c60799ea23989))
* **main:** release 1.9.3 ([#59](https://github.com/rknightion/.github/issues/59)) ([8c1e891](https://github.com/rknightion/.github/commit/8c1e89103d1a86179c2e94356b85bedd7c543a42))
* **main:** release 1.9.4 ([#61](https://github.com/rknightion/.github/issues/61)) ([bc58399](https://github.com/rknightion/.github/commit/bc58399e49a8d8131a379f530fffe8c9659667f9))
* **main:** release 1.9.5 ([#62](https://github.com/rknightion/.github/issues/62)) ([510f11e](https://github.com/rknightion/.github/commit/510f11ef9cd1b707ec6d48870b8c7efcd4a3be04))
* **main:** release 1.9.6 ([#64](https://github.com/rknightion/.github/issues/64)) ([71aced7](https://github.com/rknightion/.github/commit/71aced73a92eed12a3483ebe8fb5e59877a119fb))
* **main:** release 1.9.7 ([#66](https://github.com/rknightion/.github/issues/66)) ([ff89dc2](https://github.com/rknightion/.github/commit/ff89dc29cee6fbe49128a19715ee3f60390be0dc))
* **main:** release 1.9.8 ([#68](https://github.com/rknightion/.github/issues/68)) ([0e56520](https://github.com/rknightion/.github/commit/0e56520d848f5fda8cbfa0bda17797ef41f2a5a7))
* **main:** release 1.9.9 ([#69](https://github.com/rknightion/.github/issues/69)) ([414aeb8](https://github.com/rknightion/.github/commit/414aeb877c157ce559592551b222bbd90db61ce7))
* migrate issue tracking to Backlog.md, archive closed issues ([d207874](https://github.com/rknightion/.github/commit/d207874ba8d15fed9d9ec3c11b7957139e1a293d))
* remove Snyk reusable workflow ([4958f0f](https://github.com/rknightion/.github/commit/4958f0f897bc3540af5f52029bd4a3672fe292be))
* **tracker:** add GHC-0002 for the release automation work ([35e7db7](https://github.com/rknightion/.github/commit/35e7db7ab55e014fe9c72747391b2d5bfe0d0414))
* **tracker:** record the rollout inventory and the defects it surfaced ([89acacb](https://github.com/rknightion/.github/commit/89acacbc1a7c902d84cb3a81b71ed78c7beefb4c))

## [1.16.0](https://github.com/rknightion/.github/compare/v1.15.1...v1.16.0) (2026-08-29)


### Features

* **ci:** add the just task surface ([4497319](https://github.com/rknightion/.github/commit/4497319d950b5cc0cc15aa5cc6566f9f38b5841d))


### Miscellaneous

* **hooks:** retire the repo-local Backlog guard for the global one ([8e44ba3](https://github.com/rknightion/.github/commit/8e44ba3d6041a9644022e57b47fb55bff7dc539b))

## [1.15.1](https://github.com/rknightion/.github/compare/v1.15.0...v1.15.1) (2026-08-29)


### Miscellaneous

* **backlog:** open the parent task for the fleet justfile campaign ([1ee377f](https://github.com/rknightion/.github/commit/1ee377f1d46911a2e8b6d50241c634461aec794d))

## [1.15.0](https://github.com/rknightion/.github/compare/v1.14.0...v1.15.0) (2026-08-29)


### Features

* **fleet:** enable the weekly settings drift cron ([397938b](https://github.com/rknightion/.github/commit/397938b6e6fbf78ca4a888fc2034c988d3923d29))

## [1.14.0](https://github.com/rknightion/.github/compare/v1.13.0...v1.14.0) (2026-08-29)


### Features

* **helm-validate:** add a shared chart lint + render + schema-validation reusable ([905df03](https://github.com/rknightion/.github/commit/905df031654bc6927eb8339c6035c3b340d141ec))


### Miscellaneous

* **fleet:** record the settings audit as clean ([98d6a92](https://github.com/rknightion/.github/commit/98d6a921f2018ead7b86ca4b3fbb1c50e4f6e818))

## [1.13.0](https://github.com/rknightion/.github/compare/v1.12.0...v1.13.0) (2026-08-29)


### Features

* **fleet:** switch on the weekly repo-settings drift report ([908b3d6](https://github.com/rknightion/.github/commit/908b3d6d7937b437db5f835836cb5c85f7c3a8ee))


### Bug Fixes

* **fleet:** grant id-token: write so the broker can mint ([1ddef41](https://github.com/rknightion/.github/commit/1ddef41375c4ee91624c4435f41cc2ebbb813580))
* **fleet:** park the drift cron until the App holds administration ([560656e](https://github.com/rknightion/.github/commit/560656ee53d475d7d4e7f096e13567600871e802))
* **fleet:** pass Tailscale identity to the broker on a hosted runner ([0772de6](https://github.com/rknightion/.github/commit/0772de69029b54445a9549142148e0f46c4f2bd8))


### Build & CI

* **deps:** update actions/upload-artifact action to v7 ([#78](https://github.com/rknightion/.github/issues/78)) ([df98e2a](https://github.com/rknightion/.github/commit/df98e2a76d1e34e94e0f28e9583832c1536488f2))

## [1.12.0](https://github.com/rknightion/.github/compare/v1.11.0...v1.12.0) (2026-08-29)


### Features

* **fleet:** audit public repo settings and report drift ([9a79bbc](https://github.com/rknightion/.github/commit/9a79bbcb07aeb9e3d43b206e102801eed9f781ea))

## [1.11.0](https://github.com/rknightion/.github/compare/v1.10.1...v1.11.0) (2026-08-29)


### Features

* **auto-rc:** add sha input so callers can trigger on workflow_run ([ec685e0](https://github.com/rknightion/.github/commit/ec685e063babbaed1917883cfa8dd7f0a88d8533))


### Miscellaneous

* **backlog:** ratify ci as the sanctioned superset of check ([2802e25](https://github.com/rknightion/.github/commit/2802e25ea6be027d934f463608e65f0b9e95d5db))

## [1.10.1](https://github.com/rknightion/.github/compare/v1.10.0...v1.10.1) (2026-08-29)


### Build & CI

* **deps:** update rknightion/.github action to v1.9.8 ([#73](https://github.com/rknightion/.github/issues/73)) ([8512368](https://github.com/rknightion/.github/commit/851236813e0534dfe9f24aca502e9cbc9f3d5be0))


### Miscellaneous

* **backlog:** add GHC-0004 — harvest egress audits, then move to block mode ([0f93339](https://github.com/rknightion/.github/commit/0f93339c6927ae51c478587852b6a9f21acd1cf1))

## [1.10.0](https://github.com/rknightion/.github/compare/v1.9.11...v1.10.0) (2026-08-29)


### Features

* **ghcr-cleanup:** add runs-on and harden inputs for self-hosted callers ([9dd6053](https://github.com/rknightion/.github/commit/9dd6053b99d7d52d042f96acb1c7349ab9b9e817))

## [1.9.11](https://github.com/rknightion/.github/compare/v1.9.10...v1.9.11) (2026-08-29)


### Miscellaneous

* **backlog:** wire the fleet migration ordering into this task ([ce2749f](https://github.com/rknightion/.github/commit/ce2749f15452f38f51bbfa71836b6927bb05336a))

## [1.9.10](https://github.com/rknightion/.github/compare/v1.9.9...v1.9.10) (2026-08-29)


### Build & CI

* **deps:** update anchore/sbom-action action to v0.24.2 ([#70](https://github.com/rknightion/.github/issues/70)) ([5ab9bc0](https://github.com/rknightion/.github/commit/5ab9bc001bc6c4dd397a02e56711c5689bd66a0f))

## [1.9.9](https://github.com/rknightion/.github/compare/v1.9.8...v1.9.9) (2026-08-28)


### Miscellaneous

* **backlog:** add GHC-0003 — migrate the repo task surface to just ([a38cc71](https://github.com/rknightion/.github/commit/a38cc71c2081a2893b0b95cf28666ad2a2c56e44))

## [1.9.8](https://github.com/rknightion/.github/compare/v1.9.7...v1.9.8) (2026-08-28)


### Build & CI

* **deps:** update anchore/sbom-action action to v0.24.1 ([#67](https://github.com/rknightion/.github/issues/67)) ([edf55fa](https://github.com/rknightion/.github/commit/edf55fa2f7ec23844253c618ad7136780143bbde))

## [1.9.7](https://github.com/rknightion/.github/compare/v1.9.6...v1.9.7) (2026-08-27)


### Build & CI

* **deps:** update github/codeql-action action to v4.37.9 ([#65](https://github.com/rknightion/.github/issues/65)) ([ae38515](https://github.com/rknightion/.github/commit/ae385159ce6a835c58fff92b32387def65a49924))

## [1.9.6](https://github.com/rknightion/.github/compare/v1.9.5...v1.9.6) (2026-08-25)


### Build & CI

* **deps:** update hadolint/hadolint-action action to v3.5.0 ([#63](https://github.com/rknightion/.github/issues/63)) ([b9f5d34](https://github.com/rknightion/.github/commit/b9f5d3461064bbdb12ea6e4cc9e7b51e9e868937))

## [1.9.5](https://github.com/rknightion/.github/compare/v1.9.4...v1.9.5) (2026-08-24)


### Build & CI

* bump the broker-token action pin ([d97ef42](https://github.com/rknightion/.github/commit/d97ef42f9c9649a34137870d05fae8cb206d8fc0))

## [1.9.4](https://github.com/rknightion/.github/compare/v1.9.3...v1.9.4) (2026-08-24)


### Build & CI

* **deps:** update dependency goreleaser/goreleaser to v2.18.0 ([#60](https://github.com/rknightion/.github/issues/60)) ([d998d32](https://github.com/rknightion/.github/commit/d998d32c78aeb3e0ec0b434bec910b147136418d))

## [1.9.3](https://github.com/rknightion/.github/compare/v1.9.2...v1.9.3) (2026-08-24)


### Bug Fixes

* **actions:** fail clearly on unresolved Bao host ([f2c547a](https://github.com/rknightion/.github/commit/f2c547ab3f199be26bd439664edaa16cd72450d1))

## [1.9.2](https://github.com/rknightion/.github/compare/v1.9.1...v1.9.2) (2026-08-22)


### Build & CI

* **deps:** update github/codeql-action action to v4.37.8 ([#57](https://github.com/rknightion/.github/issues/57)) ([3807359](https://github.com/rknightion/.github/commit/3807359bfb67ad88b8b3853ce19a6d4562060a5d))

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
