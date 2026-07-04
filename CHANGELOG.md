# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-07-04

### Fixed
- Reconnect on a dropped Postgres connection instead of crashing. A long backfill
  left the connection idle between SUC API calls until the server dropped it, and
  the error handler's own `rollback()` then died — exiting the process. Added libpq
  keepalives and a reconnect-on-drop path.
- Pace SUC API requests (`SUC_MIN_REQUEST_INTERVAL_S`, default 1.1s) so a bulk
  backfill stays under the API's 60/min rate limit rather than exhausting the
  reactive 429 retry and skipping charges.

## [0.1.0] - 2026-07-04

### Added
- Initial public release: corrects TeslaMate Supercharger charge costs using
  time-of-use pricing from the SUC API.
- Docker image, docker-compose, and Kubernetes deploy manifest.
- CI (pytest) and Docker release pipelines publishing to GHCR.

[Unreleased]: https://github.com/megabitus98/teslamate-suc-cost-sync/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/megabitus98/teslamate-suc-cost-sync/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/megabitus98/teslamate-suc-cost-sync/releases/tag/v0.1.0
