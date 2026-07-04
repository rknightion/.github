# Changelog

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
