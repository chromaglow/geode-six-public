#!/bin/bash
# Setup USB backup drive for Geode Six
# Usage: sudo ./setup_usb_backup.sh /dev/sdX
#
# This script:
#   1. Formats the USB drive as ext4 with label GEODE-BACKUP
#   2. Creates the mount point /mnt/usb-backup
#   3. Installs a udev rule for automount on plug-in
#   4. Adds rsync cron job for 15-minute backups
#   5. Adds weekly index validation cron job

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: sudo $0 /dev/sdX"
    echo "  Example: sudo $0 /dev/sdb"
    echo ""
    echo "WARNING: This will FORMAT the drive. All data will be lost."
    echo "Available drives:"
    lsblk -d -o NAME,SIZE,MODEL
    exit 1
fi

DEVICE="$1"

echo "=== Geode Six USB Backup Setup ==="
echo ""
echo "WARNING: This will FORMAT ${DEVICE} and erase all data!"
echo "Device to format:"
lsblk "${DEVICE}" -o NAME,SIZE,MODEL
echo ""
read -p "Are you sure? (type YES to continue): " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    echo "Aborted."
    exit 1
fi

# Step 1: Format as ext4 with label
echo ""
echo "[1/5] Formatting ${DEVICE}1 as ext4 with label GEODE-BACKUP..."
# Create partition if needed
if ! lsblk "${DEVICE}1" &>/dev/null; then
    echo "Creating partition..."
    parted "${DEVICE}" --script mklabel gpt mkpart primary ext4 0% 100%
    sleep 2
fi
mkfs.ext4 -L GEODE-BACKUP "${DEVICE}1"
echo "Done."

# Step 2: Create mount point
echo ""
echo "[2/5] Creating mount point /mnt/usb-backup..."
mkdir -p /mnt/usb-backup
echo "Done."

# Step 3: Install udev rule for automount
echo ""
echo "[3/5] Installing udev rule for automount..."
cat > /etc/udev/rules.d/99-usb-backup.rules << 'EOF'
# Automount USB drive labeled GEODE-BACKUP for Geode Six backup
ACTION=="add", ENV{ID_FS_LABEL}=="GEODE-BACKUP", RUN+="/bin/mount -o defaults,noatime /dev/%k /mnt/usb-backup"
ACTION=="remove", ENV{ID_FS_LABEL}=="GEODE-BACKUP", RUN+="/bin/umount /mnt/usb-backup"
EOF
udevadm control --reload-rules
udevadm trigger
echo "Done."

# Step 4: Add rsync cron job (every 15 minutes)
echo ""
echo "[4/5] Adding rsync backup cron job (every 15 minutes)..."
CRON_BACKUP="*/15 * * * * /usr/bin/rsync -av --ignore-errors /mnt/nvme/gca/ /mnt/usb-backup/gca/ >> /mnt/nvme/logs/backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "rsync.*usb-backup"; echo "$CRON_BACKUP") | crontab -
echo "Done."

# Step 5: Add weekly index validation cron job
echo ""
echo "[5/5] Adding weekly index validation cron job (Sunday 2 AM)..."
CRON_VALIDATE="0 2 * * 0 /usr/bin/python3 /path/to/geode-six/scripts/validate_index.py >> /mnt/nvme/logs/index_validation.log 2>&1"
(crontab -l 2>/dev/null | grep -v "validate_index"; echo "$CRON_VALIDATE") | crontab -
echo "Done."

# Mount the drive now
echo ""
echo "Mounting drive..."
mount "${DEVICE}1" /mnt/usb-backup
mkdir -p /mnt/usb-backup/gca

echo ""
echo "=== USB Backup Setup Complete ==="
echo "  Drive: ${DEVICE}1 (label: GEODE-BACKUP)"
echo "  Mount: /mnt/usb-backup"
echo "  Backup: rsync every 15 minutes"
echo "  Validation: weekly Sunday 2 AM"
echo ""
echo "The drive will automount on plug-in."
