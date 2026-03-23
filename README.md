# Geode Six

A local-first AI document archive and assistant.  
Runs on an NVIDIA Jetson Orin Nano 8GB with Ollama — no cloud dependencies required.

## Hardware Requirements

- **NVIDIA Jetson Orin Nano 8GB** ("Six")
- Ubuntu 22.04 / JetPack 6.2
- NVMe storage mounted at `/mnt/nvme/`
- USB backup drive labeled `GEODE-BACKUP` (optional)

## Prerequisites

- **Ollama** installed and running
- Models already downloaded:
  - `llama3.1:8b-instruct-q4_0` — primary assistant
  - `dolphin-mistral` — uncensored fallback
  - `cniongolo/biomistral` — biomedical topics
  - `llava:7b-v1.6-mistral-q4_0` — vision/image queries
- **Python 3.10+** (JetPack 6.2 default)

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/chromaglow/geode-six-public.git geode-six
cd geode-six

# 2. Create environment file
cp .env.example .env
# Edit .env with your paths if different from defaults

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Build Ollama modelfiles
chmod +x scripts/build_modelfiles.sh
./scripts/build_modelfiles.sh

# 5. Start the router service
sudo cp systemd/geode-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now geode-router.service
```

## One-Time Google Drive Import

If you overlap existing flat `v1` folders, use the migration script to upgrade them to the Two-Tier system:
```bash
python scripts/migrate_to_v2.py
```

If you have brand new files to import from Google Drive:
```bash
python scripts/import_gca.py --source /path/to/google-drive-download
```

This will:
1. Iterate all files recursively
2. AI-assign tier, project code, type code, description, and date
3. Save each file to the correct `/mnt/nvme/gca/[TIER]/[PROJECT]/` subfolder
4. Run a full Chroma embedding pass
5. Print a summary of files processed, skipped, and errors

## USB Backup Setup

```bash
# Format and label a USB drive as GEODE-BACKUP
chmod +x scripts/setup_usb_backup.sh
sudo ./scripts/setup_usb_backup.sh /dev/sdX   # replace with your USB device

# The udev rule will automount the drive on plug-in
# rsync runs every 15 minutes via cron
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Ollama status, model availability, RAM available |
| `POST` | `/query` | Send prompt to router, get AI response |
| `POST` | `/gca/upload` | Upload file, get AI name suggestion for review |
| `POST` | `/gca/confirm` | User confirms or edits fields, file is committed |
| `POST` | `/gca/search` | Natural language search over GCA |
| `GET` | `/gca/browse` | List files with filter and sort params |
| `GET` | `/gca/codes` | Return dynamic project/operation codes |
| `POST` | `/gca/folder/create` | Create a new project or operation folder |
| `GET` | `/gca/download` | Securely download a file by its `path` |

## Web UI

Access the web UI at `http://localhost:8000` (local) or `https://example.com` (remote via Cloudflare Tunnel).

Four sections:
- **Assistant** — Chat with AI models (Llama 3.1, BioMistral, Dolphin)
- **Upload** — Drag-and-drop file upload with AI naming
- **Browse** — Filter and sort all GCA files
- **Search** — Natural language semantic search with optional AI summaries

## Cloudflare Tunnel (Remote Access)

Remote access is provided via Cloudflare Tunnel at `example.com`.

**Access levels:**
- **admin@example.com** — full access to all endpoints
- **user1@example.com, user2@example.com** — web UI access only (no SSH, no admin endpoints)

**Setup:**
```bash
# Install cloudflared (already on Jetson)
sudo cp systemd/cloudflared.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
```

Configure Cloudflare Access policies in the Cloudflare Zero Trust dashboard:
1. Create an Access application for `example.com`
2. Add email OTP authentication
3. Create policies: allow admin@example.com full access, allow user1@example.com and user2@example.com web-only access

## Troubleshooting

### Ollama not responding
```bash
sudo systemctl status ollama
sudo systemctl restart ollama
# Check: curl http://localhost:11434/api/tags
```

### USB not mounting
```bash
# Check if udev rule exists
cat /etc/udev/rules.d/99-usb-backup.rules
# Check drive label
lsblk -o NAME,LABEL,MOUNTPOINT
# Manually mount
sudo mount /dev/sdX1 /mnt/usb-backup
```

### Chroma index rebuild
```bash
# Validate existing index
python scripts/validate_index.py

# Full re-index (delete Chroma data and re-embed all files)
rm -rf /mnt/nvme/chroma/*
python scripts/import_gca.py --source /mnt/nvme/gca
```

### Router not starting
```bash
sudo systemctl status geode-router
sudo journalctl -u geode-router -n 50
# Check if port 8000 is in use
sudo lsof -i :8000
```
