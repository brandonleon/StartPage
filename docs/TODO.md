# TODO: CVE-2026-44431 urllib3 Security Fix

## Status
- [x] Reviewed `claude/investigate-cve-2026-44431-eJJ7O` branch
- [x] Merged fix into `develop` (commit `9f20c83`)
  - Resolved conflict: kept `httpx>=0.28.1`, added `urllib3>=2.7.0,<3.0.0`
  - Lock file regenerated: `urllib3 2.6.1 → 2.7.0`
- [x] Bumped version to `2.8.0a1` (commit `7cb39ab`)
- [x] Pushed `develop` to remote
- [ ] Push current `develop` commits to remote
- [ ] When ready to release: merge `develop` → `main` as `2.8.0`
  - `main` is still on v2.7.0 (unpatched); the CVE fix ships with 2.8.0

## Context
- **CVE-2026-44431**: `urllib3 < 2.7.0` leaks `Authorization`/`Cookie` headers
  across cross-origin redirects when using `urllib3.ProxyManager`.
- This project does not use `ProxyManager` directly; exposure is low but the
  pin is correct defense-in-depth.
- Decision: no hotfix to `main`; CVE fix ships with the 2.8.0 release.
