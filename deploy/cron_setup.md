# Index Update Scheduling Guide

This document explains how to set up automated daily updates for the knowledge base index.

## Prerequisites

- Python environment configured (`uv sync` completed)
- `make` command available
- Project directory accessible

---

## Option 1: Unix Cron (Linux/macOS)

### Setup

```bash
# Open crontab editor
crontab -e

# Add daily job at 6:00 AM (adjust path to your project)
0 6 * * * cd /path/to/architecture-pro-quantum-forge && make update-index >> logs/cron.log 2>&1
```

### Verify

```bash
# List current cron jobs
crontab -l
```

### Troubleshooting

- Ensure `PATH` includes `uv` and `python`
- Check `logs/cron.log` for errors
- Verify project path is absolute

---

## Option 2: Launchd (macOS Recommended)

Launchd is more reliable on macOS and handles system sleep/wake.

### Create Plist File

```bash
cat > ~/Library/LaunchAgents/com.quantumforge.update-index.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.quantumforge.update-index</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/path/to/architecture-pro-quantum-forge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-c</string>
        <string>source ~/.zshrc && make update-index</string>
    </array>
    <key>StandardOutPath</key>
    <string>/path/to/architecture-pro-quantum-forge/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/architecture-pro-quantum-forge/logs/launchd-error.log</string>
</dict>
</plist>
EOF
```

### Load and Enable

```bash
# Load the job
launchctl load ~/Library/LaunchAgents/com.quantumforge.update-index.plist

# Test manually
launchctl start com.quantumforge.update-index

# Check status
launchctl list | grep quantumforge
```

### Unload (if needed)

```bash
launchctl unload ~/Library/LaunchAgents/com.quantumforge.update-index.plist
```

---

## Option 3: Docker/Kubernetes

For production deployments, use a Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: knowledge-base-update
spec:
  schedule: "0 6 * * *"  # Daily at 6:00 UTC
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: updater
            image: quantum-forge-rag:latest
            command: ["make", "update-index"]
            volumeMounts:
            - name: knowledge-base
              mountPath: /app/knowledge_base
            - name: vector-db
              mountPath: /app/data/chroma_storage
          restartPolicy: OnFailure
          volumes:
          - name: knowledge-base
            persistentVolumeClaim:
              claimName: knowledge-base-pvc
          - name: vector-db
            persistentVolumeClaim:
              claimName: vector-db-pvc
```

---

## Manual Execution

Run update manually any time:

```bash
make update-index
```

---

## Log Files

| File | Description |
|------|-------------|
| `logs/update_index.log` | JSON log entries from update script |
| `logs/cron.log` | Cron stdout/stderr |
| `logs/launchd.log` | Launchd stdout |

### Log Format

```json
{
  "timestamp": "2025-07-17T06:00:00Z",
  "status": "success",
  "files_scanned": 32,
  "files_added": 3,
  "files_updated": 1,
  "files_deleted": 0,
  "chunks_indexed": 45,
  "index_size": 1250,
  "duration_seconds": 12.5,
  "errors": []
}
```

---

## Error Handling

The update script:
1. Logs all errors to `logs/update_index.log`
2. Continues processing even if individual files fail
3. Reports final status as `success`, `partial_success`, or `failed`

For critical failures, consider adding alerting:

```bash
# In crontab, add email notification
MAILTO=admin@example.com
0 6 * * * cd /path/to/project && make update-index || echo "Update failed"
```
