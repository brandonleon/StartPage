# Dependabot Vulnerability Alerts

> **Source**: [GitHub Dependabot Alerts](https://github.com/brandonleon/StartPage/security/dependabot)  
> **Last updated**: 2026-05-20  
> **Total open alerts**: 14 (7 high, 7 moderate)

---

## High Severity

| # | CVE | Package | Vulnerable Range | Patched Version | CVSS | Summary |
|---|-----|---------|-------------------|-----------------|------|---------|
| 58 | CVE-2026-44431 | urllib3 | >= 1.23, < 2.7.0 | 2.7.0 | 5.3 | Sensitive headers forwarded across origins in proxied low-level redirects |
| 57 | CVE-2026-44432 | urllib3 | >= 2.6.0, < 2.7.0 | 2.7.0 | 7.5 | Decompression-bomb safeguards bypassed in parts of the streaming API |
| 56 | CVE-2026-42561 | python-multipart | < 0.0.27 | 0.0.27 | 7.5 | Denial of Service via unbounded multipart part headers |
| 51 | CVE-2026-24486 | python-multipart | < 0.0.22 | 0.0.22 | 8.6 | Arbitrary File Write via Non-Default Configuration |
| 50 | CVE-2026-21441 | urllib3 | >= 1.22, < 2.6.3 | 2.6.3 | 7.5 | Decompression-bomb safeguards bypassed when following HTTP redirects (streaming API) |
| 48 | CVE-2024-47874 | starlette | < 0.40.0 | 0.40.0 | — | Denial of service (DoS) via multipart/form-data |
| 46 | CVE-2023-30798 | starlette | < 0.25.0 | 0.25.0 | 7.5 | MultipartParser denial of service with too many fields or files |

## Moderate Severity

| # | CVE | Package | Vulnerable Range | Patched Version | CVSS | Summary |
|---|-----|---------|-------------------|-----------------|------|---------|
| 59 | CVE-2026-45409 | idna | < 3.15 | 3.15 | — | Specially crafted inputs to idna.encode() can bypass CVE-2024-3651 fix |
| 55 | CVE-2026-28684 | python-dotenv | < 1.2.2 | 1.2.2 | 6.6 | Symlink following in set_key allows arbitrary file overwrite via cross-device rename fallback |
| 54 | CVE-2026-40347 | python-multipart | < 0.0.26 | 0.0.26 | 5.3 | Denial of Service via large multipart preamble or epilogue data |
| 53 | CVE-2025-71176 | pytest | < 9.0.3 | 9.0.3 | 6.8 | Vulnerable tmpdir handling |
| 52 | CVE-2026-25645 | requests | < 2.33.0 | 2.33.0 | 4.4 | Insecure Temp File Reuse in extract_zipped_paths() utility function |
| 49 | CVE-2025-54121 | starlette | < 0.47.2 | 0.47.2 | 5.3 | Possible denial-of-service vector when parsing large files in multipart forms |
| 47 | CVE-2023-29159 | starlette | >= 0.13.5, < 0.27.0 | 0.27.0 | 3.7 | Path Traversal vulnerability in StaticFiles |

---

## Remediation Priority

### Immediate — Upgrade these first (high severity, directly exploitable)

1. **urllib3** → `>= 2.7.0` — Fixes CVE-2026-44431, CVE-2026-44432, and CVE-2026-21441
2. **python-multipart** → `>= 0.0.27` — Fixes CVE-2026-42561, CVE-2026-24486, and CVE-2026-40347
3. **starlette** → `>= 0.47.2` — Fixes CVE-2024-47874, CVE-2025-54121, CVE-2023-30798, and CVE-2023-29159

### Secondary — Upgrade when convenient (moderate severity)

4. **idna** → `>= 3.15`
5. **python-dotenv** → `>= 1.2.2`
6. **requests** → `>= 2.33.0`
7. **pytest** → `>= 9.0.3` (dev dependency)

---

## Applicability Analysis

Investigated the codebase to determine which vulnerabilities actually apply to StartPage's usage patterns.

### ✅ Directly applicable (7 of 14)

| # | CVE | Package | Why it applies |
|---|-----|---------|----------------|
| 58 | CVE-2026-44431 | urllib3 | Direct dependency — pinned `>=2.7.0,<3.0.0` in pyproject.toml. Already patched on `develop`. |
| 57 | CVE-2026-44432 | urllib3 | Same as above — single upgrade to 2.7.0 resolves both. |
| 50 | CVE-2026-21441 | urllib3 | Same as above — already on 2.7.0 in lock file. |
| 46 | CVE-2023-30798 | starlette | Starlette 0.52.1 is installed (via FastAPI). App uses `Form()`, `UploadFile`, and `File()` extensively — directly triggers MultipartParser. **Already on 0.52.1 (>=0.25.0). Dependabot reads from `main` branch.** |
| 48 | CVE-2024-47874 | starlette | Same — multipart/form-data DoS applies. **Already on 0.52.1 (>=0.40.0). Dependabot reads from `main` branch.** |
| 49 | CVE-2025-54121 | starlette | Same — large file multipart DoS applies. **Already on 0.52.1 (>=0.47.2). Dependabot reads from `main` branch which pins old FastAPI.** |
| 56 | CVE-2026-42561 | python-multipart | Direct dependency (`>=0.0.22`). App uses `Form()` and `UploadFile` — unbounded multipart headers directly exploitable. **Fixed: upgraded to 0.0.29.** |

### ⚠️ Indirectly applicable (3 of 14)

| # | CVE | Package | Why it may apply |
|---|-----|---------|----------------|
| 51 | CVE-2026-24486 | python-multipart | Direct dependency, but "Arbitrary File Write via Non-Default Configuration" — only exploitable with non-default upload dir. Verify app config. |
| 54 | CVE-2026-40347 | python-multipart | Direct dependency, but DoS via preamble/epilogue requires specific multipart payloads. Low practical risk but still valid. |
| 47 | CVE-2023-29159 | starlette | App mounts `StaticFiles(directory="static")` — path traversal applies if the static directory shares a name prefix with sibling directories. Verify local structure. |

### ❌ Not applicable (4 of 14)

| # | CVE | Package | Why it doesn't apply |
|---|-----|---------|----------------------|
| 59 | CVE-2026-45409 | idna | Only a transitive dep of `httpx`/`requests`. The app never calls `idna.encode()` directly. |
| 55 | CVE-2026-28684 | python-dotenv | Listed in pyproject.toml but `set_key()` is never called. Only `load_dotenv`-style reads are typical, which aren't affected. |
| 52 | CVE-2026-25645 | requests | `requests` is a direct dependency but **never imported or used** — the codebase uses `httpx` for HTTP calls (`services/io_utils.py`). Dead dependency. |
| 53 | CVE-2025-71176 | pytest | Dev/test dependency only — never runs in production. |

---

## Action Items

1. ~~**Upgrade `python-multipart`** to `>=0.0.27`~~ — Done. Upgraded from `0.0.22` → `0.0.29` (v2.8.0a4).
2. ~~**Upgrade `starlette`** (via FastAPI)~~ — Already resolved on `develop` (at 0.52.1). Dependabot alert is from `main` branch's old FastAPI pin (`>=0.86,<0.87`). Will resolve when `develop` merges to `main`.
3. ~~**Verify `urllib3`**~~ — Already pinned `>=2.7.0,<3.0.0` on `develop` (lock at 2.7.0). Same `main` branch issue.
4. **Remove `requests`** from pyproject.toml — unused dead dependency that brings in transitive vuln exposure.
5. **Pin `python-dotenv>=1.2.2`** — low risk (no `set_key` usage) but easy fix.
6. **Pin `pytest>=9.0.3`** — dev-only but trivial to update.
7. **Verify Starlette StaticFiles** path traversal (CVE-2023-29159) — check that no sibling directory shares a name prefix with `static/`.
8. **Merge `develop` → `main`** as v2.8.0 — resolves remaining starlette/urllib3 Dependabot alerts that read from `main`.

**Note**: `urllib3` CVEs are already resolved on `develop` (pinned to `>=2.7.0,<3.0.0`, lock file at 2.7.0). Dependabot may be reading from the `main` branch.