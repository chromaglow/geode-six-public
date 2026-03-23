# Geode Six — Phase 2 Build Spec v1.1
**Date:** 2026-03-22 | **Author:** [YOUR_NAME] | **Status:** READY FOR IMPLEMENTATION  
**Repo:** https://github.com/[YOUR_ORG]/geode-six | **Jetson:** six.local / 192.168.x.x | **Live:** https://[YOUR_DOMAIN].com

---

## Hardware Inventory

| Device | Specs | Role |
|--------|-------|------|
| Jetson Orin Nano 8GB | Ubuntu 22.04 / JetPack 6.2, FireCuda 530 512GB NVMe at /mnt/nvme/ | Always-on: GCA infra, routing, search, embeddings, fallback AI |
| Windows PC | AMD Ryzen 9 7900X3D, RTX 4080 Super 16GB VRAM, 64GB DDR5, 1TB SSD | Personal AI node: uncensored models, camera vision analysis |
| SenseCAP Watcher W1-B | ESP32-S3 + Himax WiseEye2, OV5647 120° camera, mic, speaker, Wi-Fi 2.4GHz | Presence detection, camera pipeline |

**Network:** Jetson and Windows PC are physically adjacent. Use Ethernet cable for reliability. Both on same LAN. No VPN, no cloud, no port forwarding needed.

---

## Development Conventions (carry forward from Phase 1 — never violate)

- All paths from `.env` — never hardcode `/mnt/nvme/` or any IP in application code
- No Docker, no React, no npm build steps — vanilla HTML/JS for UI, systemd for process management
- No spaces in any filename the system produces
- Backend changes require test updates — maintain 38+ passing tests at all times
- numpy pinned at 1.26.4 — do not upgrade
- Ollama `keep_alive` on Jetson stays at 5 minutes — do not remove
- `CHANGELOG.md` updated at end of each build session
- Commit messages must be descriptive and agent-readable
- Six uses she/her pronouns in all user-facing copy

---

## Model Naming Convention

All models use Geode naming in Modelfiles. Same Six system prompt convention throughout.

| Geode Name | Base Model | Location | Purpose |
|------------|-----------|----------|---------|
| geode-personal | `dolphin3.0-llama3.1:8b-q8` | Windows | [ADMIN_USER]'s daily driver — uncensored, full VRAM fit |
| geode-deep | `dolphin-llama3:70b-q4_K_M` | Windows | Optional depth model — pull later, ~20 tok/s |
| geode-vision | `llava:13b` | Windows | Camera scene analysis upgrade from Jetson 7B |
| geode-llava | existing llava:7b | Jetson | Camera fallback when Windows offline |
| (existing Jetson models) | unchanged | Jetson | Team access, GCA, fallback |

**geode-personal is the MVP model. Pull geode-deep and geode-vision after geode-personal is confirmed working.**

---

## Project 2A — Windows Ollama Setup

### What this builds
Ollama running on Windows PC, exposed on LAN so Jetson router can send queries to it.

### Step-by-step

1. Download and install Ollama from https://ollama.com on Windows
2. Set `OLLAMA_HOST` as a **system-level** environment variable (not user-level):
   - Windows 11: Settings → search "environment variables" → Edit system environment variables → Environment Variables → System variables → New
   - Variable name: `OLLAMA_HOST` | Value: `0.0.0.0`
   - **Must be system-level or the Ollama service will not see it**
3. Open Windows Firewall inbound rule for port 11434:
   - Windows Defender Firewall → Advanced Settings → Inbound Rules → New Rule
   - Rule type: Port | TCP | Specific port: 11434 | Allow the connection | All profiles | Name: "Ollama LAN"
   - **This step is critical and commonly missed. Without it, Jetson cannot reach Windows Ollama regardless of OLLAMA_HOST setting.**
4. Restart Ollama after setting environment variable (it does not pick up changes live)
5. Assign static IP to Windows PC in router DHCP settings (prevents IP changing on reboot)
6. Verify from Jetson via SSH: `curl http://<windows-ip>:11434/api/tags` — should return JSON
7. Pull models on Windows: `ollama pull dolphin3.0-llama3.1:8b-q8` (primary), others after
8. Configure Ollama Windows auto-start on login:
   - Create Windows Task Scheduler entry: runs `ollama serve` on user login, runs as current user
   - This ensures Ollama is running after reboot without manual intervention
   - **Note:** Widget (Project 2D) will provide manual start/stop override — auto-start is the default state
9. Add to `.env` on Jetson: `WINDOWS_OLLAMA_HOST=http://<windows-static-ip>:11434`
10. Build Modelfiles for Windows-hosted models using Geode naming convention and Six system prompt

### VRAM notes
- geode-personal (8B Q8): ~8.5GB VRAM — fits entirely in 16GB, ~80-100 tok/s, instant feel
- geode-deep (70B Q4_K_M): ~40GB total, splits across 16GB VRAM + DDR5 RAM, ~20 tok/s — usable but slower
- geode-vision (llava:13b): ~8GB VRAM — can load alongside geode-personal if needed

---

## Project 2B — Router Overflow Activation

### What this builds
Activates the existing Windows router stub in `router/router.py`. Routes [ADMIN_USER]'s queries to Windows. Everyone else stays on Jetson. Graceful fallback when Windows is offline.

### Routing logic

```
Request arrives at router
│
├── Is this a /camera/event POST? → always handle on Jetson, never route to Windows
├── Is this a GCA operation (upload, search, embed, browse)? → always Jetson
├── Is requester IP == [ADMIN_IP]? → route to Windows Ollama (geode-personal)
│   └── Windows offline or timeout (<3s)? → fallback to Jetson, log the fallback
└── All other IPs ([USER_1], [USER_2], unknown) → Jetson
```

### Environment variables to add to `.env`

```
WINDOWS_OLLAMA_HOST=http://<windows-static-ip>:11434
[ADMIN_IP]=<admin-local-ip>
WINDOWS_HEALTH_TIMEOUT=3
```

### Implementation

- Activate the router stub — replace placeholder with real health check + routing logic
- Health check: `GET /api/tags` on Windows Ollama with 3-second timeout
- Health check runs on every request to [ADMIN_USER]'s endpoint (not on a timer) — keeps it simple
- On Windows timeout: fall back silently, log `[ROUTING] Windows offline, falling back to Jetson`
- Update `/health` endpoint to include `windows_node: online/offline` status
- Update UI status indicator to show Windows node availability (green/grey dot is fine)
- Maintain 38+ passing tests — add tests for: Windows online routing, Windows offline fallback, GCA always-Jetson, non-[ADMIN_IP] always-Jetson

---

## Project 2C — Personal Query Endpoint

### What this builds
A dedicated `/personal/query` endpoint that [ADMIN_USER]'s browser calls when they want a personal AI conversation. Routes to Windows geode-personal. Not exposed through Cloudflare tunnel — LAN only.

### How it works
- [ADMIN_USER]'s UI has a mode indicator — "Personal" vs "Team" — toggled by a small button
- Personal mode: UI calls `/personal/query` → router sends to Windows geode-personal
- Team mode: UI calls `/query` → standard routing (Jetson for everyone)
- When Windows is offline and [ADMIN_USER] is in personal mode: return friendly message "Personal mode unavailable — Windows node is offline" rather than silent fallback
- `/personal/query` endpoint rejects requests from non-[ADMIN_IP] IPs with 403

### Cloudflare note
`/personal/query` must NOT be added to the Cloudflare tunnel exposure. It is LAN-only by design.

---

## Project 2D — SenseCAP Watcher Camera Pipeline

### Hardware connection
- Connect Watcher to Jetson via USB-C cable: Watcher bottom USB-C port (data+power) → Jetson USB port
- Watcher also needs 2.4GHz Wi-Fi for HTTP POST events — connect via SenseCraft app before doing anything else
- USB connection is for future development/firmware work; HTTP POST over Wi-Fi is the active integration method for this spec

### How the camera connects
Watcher fires HTTP POST to Jetson endpoint when detection event triggers. No custom firmware needed for this phase. Configured entirely via SenseCraft mobile app.

**POST payload structure:**
```json
{
  "prompt": "person detected at desk",
  "big_image": "<base64 encoded 640x480 JPEG, ~20-55KB>",
  "small_image": "<base64 encoded 416x416 JPEG, ~15-30KB>",
  "inference": {
    "boxes": [[x, y, w, h, score, class_id]],
    "classes": [[score, class_id]],
    "classes_name": ["person"]
  }
}
```

**Total POST size per event: ~35-85KB. LAN delivery is effectively instant.**

### Image storage — critical design decision
**Do NOT log base64 strings to camera.log.** At 30-second polling intervals, this creates gigabytes of unreadable data quickly.

Correct approach:
- Decode base64 on receipt
- Save big_image as JPEG to `/mnt/nvme/camera/YYYYMMDD_HHMMSS_big.jpg`
- Save small_image as JPEG to `/mnt/nvme/camera/YYYYMMDD_HHMMSS_small.jpg`
- Log only metadata to camera.log: `timestamp | event_text | big_image_path | small_image_path | llava_description`
- Implement log rotation: keep last 30 days of JPEGs, rotate camera.log at 10MB

### LLaVA integration — async required
LLaVA call on Jetson takes 15-40 seconds per image. The Watcher's HTTP POST will timeout if the endpoint blocks.

**Implementation: fire-and-forget async pattern**
- `/camera/event` receives POST, saves images immediately, returns HTTP 200 within 1 second
- LLaVA call happens in a background thread after the response is sent
- When LLaVA completes, result is written to camera.log and last_event state
- Use Python `threading.Thread` or `concurrent.futures.ThreadPoolExecutor` — keep it simple

### LLaVA routing
- Windows online → use geode-vision (llava:13b) on Windows 4080 for better descriptions
- Windows offline → use geode-llava (llava:7b) on Jetson as fallback
- Same async pattern either way

### New endpoints

**POST `/camera/event`**
- Validates `CAMERA_TOKEN` header (shared secret between Watcher and Six)
- Decodes and saves images
- Returns 200 immediately
- Fires async LLaVA call in background
- Rejects missing/wrong token with 401

**GET `/camera/status`**
- Returns last detection event: timestamp, event text, LLaVA description, thumbnail path
- Used by UI and widget
- LAN only — not Cloudflare exposed unless [ADMIN_USER] explicitly requests it later

### New environment variables
```
CAMERA_TOKEN=<shared_secret>
CAMERA_IMAGE_PATH=/mnt/nvme/camera
CAMERA_LOG_PATH=/mnt/nvme/logs/camera.log
CAMERA_LOG_MAX_MB=10
CAMERA_IMAGE_RETENTION_DAYS=30
```

### SenseCraft app configuration
- Connect Watcher to 2.4GHz Wi-Fi (not 5GHz — device limitation)
- Create task: "Notify me when a person is present at the desk"
- In HTTP Message Block: URL = `http://192.168.x.x:8000/camera/event`, token = CAMERA_TOKEN value
- Enable big_image in payload settings
- Starting poll interval: 30 seconds (configurable in app, not in code)

### Presence detection behavior (MVP)
- On first detection of the day: Six logs "Good morning" event, UI shows greeting
- On detection after absence >30 min: Six logs "Welcome back" event
- Both events visible in `/camera/status` and UI camera panel
- No audio/TTS in this spec — that is Phase 2.5 (XiaoZhi voice loop)

---

## Project 2E — Windows Desktop Widget

### What this builds
A lightweight always-running Python desktop application on Windows that:
- Lives in system tray normally
- Pops to front of all windows when triggered by Six (camera event or command)
- Provides one-click start/stop for Ollama
- Shows Six and Windows node status at a glance

### Technical approach
- Python with `tkinter` for the floating window + `pystray` for system tray icon
- No Electron, no browser, no heavy dependencies
- Communicates with Jetson Six via HTTP (polls `/health` and `/camera/status`)
- Communicates with local Ollama via `localhost:11434/api/tags`
- Starts on Windows login via Task Scheduler entry (created during setup)

### UI elements
```
┌─────────────────────────┐
│  ● Six     online        │
│  ● Ollama  running       │
│  Model: geode-personal   │
│                          │
│  Last event: 2 min ago   │
│  "Person at desk"        │
│                          │
│  [Start Ollama] [Stop]   │
└─────────────────────────┘
```

### Pop-to-front trigger
- Widget polls `/camera/status` every 10 seconds
- When a new event timestamp is detected, widget calls `root.lift()` and `root.attributes('-topmost', True)` to bring window to front of all open windows
- User sees event, clicks anywhere on widget or presses Escape to dismiss back to tray
- This is standard Windows behavior, no special permissions needed

### Ollama start/stop
- Start: `subprocess.Popen(['ollama', 'serve'])` — non-blocking
- Stop: `subprocess.run(['taskkill', '/IM', 'ollama.exe', '/F'])`
- Button state updates based on Ollama health check result

### Widget is a separate mini-project
- Lives in `/widget/` subdirectory of the repo
- Has its own `requirements.txt`: `pystray`, `pillow`, `requests`
- Has its own `README_WIDGET.md` with Windows setup instructions
- One-time setup: run `setup_widget.bat` which installs deps and creates Task Scheduler entry

---

## Project 2.5 — XiaoZhi Voice Integration (OUT OF SCOPE THIS SPEC)

Flagged for next spec. Key findings from research:

- W1-B is compatible with XiaoZhi firmware (the "AI Vision Edition only" restriction applies to a specific Amazon W1-A SKU, not the W1-B)
- XiaoZhi firmware enables always-listening local voice assistant with wake word
- Supports MCP protocol — can call tools like "play KEXP", "start recording", etc.
- Can be pointed at local Ollama instead of cloud
- Visual wake-up: camera detects approaching person → Watcher wakes and greets
- Firmware flash process is documented at wiki.seeedstudio.com/flash_watcher_agent_firmware
- This is a clean, self-contained project — deserves its own spec

Do not implement any part of this in Phase 2.

---

## Out of Scope for This Spec

- Voice loop (Whisper STT + Piper TTS) — separate spec
- NeMo orchestration — blocked on upstream Jetson GPU detection bug
- Google Drive ongoing sync — deferred
- Cloud backup (S3/Drive) — deferred
- Health alert notifications — deferred
- Fine-grained gesture recognition — deferred
- Wake-on-LAN (not needed — PC stays awake, screens sleep only)

---

## Implementation Sequence

| Phase | Task | Effort | Dependency |
|-------|------|--------|------------|
| 2A | Windows Ollama install, firewall, static IP, model pull | 1-2 hrs | None — do first |
| 2B | Activate router stub, health check, IP-based routing, fallback | 2-3 hrs | 2A complete |
| 2C | /personal/query endpoint, UI personal/team toggle | 1-2 hrs | 2B complete |
| 2D | Camera pipeline: endpoint, async LLaVA, image storage, log rotation | 3-4 hrs | 2A for geode-vision routing |
| 2E | Windows widget: tray app, pop-to-front, start/stop Ollama | 2-3 hrs | 2A, 2D for event trigger |

**Total estimate: 1.5-2 days of focused build time.**  
**Recommended order: 2A → 2B → 2D → 2C → 2E**

---

## Acceptance Criteria

- [ ] `curl http://<windows-ip>:11434/api/tags` returns JSON from Jetson SSH session
- [ ] [ADMIN_USER]'s browser IP routes to geode-personal on Windows (verify via response header or log)
- [ ] Non-[ADMIN_USER] IP routes to Jetson model (verify with different device on network)
- [ ] Windows offline → [ADMIN_USER] gets graceful fallback message, not a crash
- [ ] `/personal/query` returns 403 from non-[ADMIN_IP] IP
- [ ] POST to `/camera/event` with valid token returns 200 within 1 second
- [ ] POST to `/camera/event` with invalid token returns 401
- [ ] JPEG files appear in `/mnt/nvme/camera/` after camera event
- [ ] `camera.log` contains metadata only — no base64 strings
- [ ] LLaVA description appears in log within 60 seconds of event
- [ ] `/camera/status` returns last event data
- [ ] Widget appears on Windows desktop and shows correct Six + Ollama status
- [ ] Widget pops to front within 10 seconds of new camera event
- [ ] Ollama starts and stops correctly from widget buttons
- [ ] 38+ tests passing after all changes
- [ ] `CHANGELOG.md` updated

---

## References

- SenseCAP Watcher Wiki: https://wiki.seeedstudio.com/watcher/
- Watcher Software Framework (payload spec): https://wiki.seeedstudio.com/watcher_software_framework/
- XiaoZhi firmware flash guide: https://wiki.seeedstudio.com/flash_watcher_agent_firmware/
- Ollama Windows env vars: https://docs.ollama.com/faq
- dolphin3.0-llama3.1 on Ollama: https://ollama.com/CognitiveComputations/dolphin-llama3.1
- Six repo: https://github.com/chromaglow/six_archive
