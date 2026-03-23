# Changelog — Geode Six

All notable changes to this project will be documented in this file.

## [2.0.0] — 2026-03-22

### Restructured GCA System (Two-Tier Layout)
- Replaced flat folder structure with a two-tier layout:
  - `Projects/` (e.g., PR5, PR6, GEO, PR4)
  - `Operations/` (e.g., ARC, CON, HR, LDS)
- Built `gca/codes.py` to dynamically load project and operation codes from `codes.json`.
- Updated AI naming prompt to dynamically use codes from `codes.json` for increased accuracy.
- Added `POST /gca/folder/create` endpoint to allow users to create new project/operation folders from the UI.
- Updated `gca/embed.py` and `gca/search.py` to traverse the new two-tier structure and index a new `tier` metadata field in Chroma.
- Updated the Search and Browse UI to include a Scope/Tier toggle (All, Projects, Operations) and display Tier badges.
- Created `scripts/migrate_to_v2.py` for performing the data migration from v1 to v2.
- Updated `scripts/import_gca.py` to support routing into the v2 structure and added a `--tier` force flag.
- Fixed Browse filters to properly filter by Project/Operation tiers and added active toggle states.
- Fixed dynamic code loading in the UI dropdowns, including correct optgroup behavior.
- Expanded type code dropdowns to display full descriptive labels instead of abbreviations.
- Added a compact, inline "New Folder" creation link to the Upload UI with client-side validation and success messaging.
- Upgraded the Upload UI to support batch file uploads (up to 5 files simultaneously) with unified sequential confirmation logic and progress states.
- Rewrite upload flow — fix batch/single conflict, sequential processing, stuck state reset
- Fix Confirm All button in batch upload flow

## [1.1.0] — 2026-03-21

### File Downloads
- Added `GET /gca/download?path=` endpoint with security validation
  - Only serves files under `GCA_ROOT` — rejects path traversal with 403
  - Returns plain English "File not found" for missing files (404)
- Filenames in Browse and Search sections are now clickable download links
- Added `path` field to browse response for download link construction
- 3 new download tests: valid file (200), path outside GCA (403), missing file (404)

## [1.0.0] — 2026-03-21

### Milestone 1 — Modelfiles + Router
- Created Ollama Modelfiles for Llama 3.1, Dolphin-Mistral, BioMistral, and LLaVA
- Built `scripts/build_modelfiles.sh` to register all models with Ollama
- Implemented `router/router.py` — FastAPI router with:
  - Smart model routing (image→LLaVA, bio keywords→BioMistral, sensitive→Dolphin, default→Llama)
  - `/health` endpoint with model availability and RAM monitoring
  - RAM guard (returns friendly "busy" message below threshold)
  - Structured JSON logging (timestamp, model, latency, tokens)
- Created `systemd/geode-router.service` for boot and restart management
- 12 router tests passing

### Milestone 2 — Remote Access
- Created `systemd/cloudflared.service` for Cloudflare Tunnel ([YOUR_DOMAIN].com)
- Documented Cloudflare Access setup with email OTP for [ADMIN_USER] (full), [USER_1]/[USER_2] (web-only)

### Milestone 3 — GCA File Intake + USB Backup
- Implemented `gca/intake.py` — two-step upload/confirm flow:
  - AI-powered file naming via Llama 3.1
  - 5-level date resolution priority (user note → metadata → filename → ctime → today)
  - Duplicate detection and version management
  - Text extraction from PDF, DOCX, TXT, MD, XLSX, images
- Built `scripts/import_gca.py` for one-time Google Drive import
- Built `scripts/setup_usb_backup.sh` with udev automount and rsync cron
- 17 intake tests passing

### Milestone 4 — Semantic Search + Index Validation
- Implemented `gca/embed.py` — text chunking + Chroma embedding via nomic-embed-text
  - Falls back to sentence-transformers/all-MiniLM-L6-v2 if Ollama embedding unavailable
- Implemented `gca/search.py`:
  - `POST /gca/search` — semantic search with optional AI synthesis
  - `GET /gca/browse` — file listing with project/type filters and sorting
- Built `scripts/validate_index.py` for weekly Chroma index cleanup
- 9 browse/search tests passing

### Milestone 5 — Web UI
- Built `ui/index.html`, `ui/style.css`, `ui/app.js` — vanilla HTML/CSS/JS SPA
- Four sections: Assistant (chat), Upload (drag-and-drop), Browse (filtered list), Search (semantic)
- Dark mode with Inter font, project-colored badges, micro-animations
- Mobile-first responsive (390px+), large tap targets
- No build step, no npm, no React
