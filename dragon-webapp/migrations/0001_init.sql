CREATE TABLE IF NOT EXISTS meeting_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT,meeting_date TEXT NOT NULL,venue TEXT NOT NULL,model_version TEXT NOT NULL,captured_at TEXT NOT NULL,source_url TEXT NOT NULL,payload TEXT NOT NULL,locked INTEGER NOT NULL DEFAULT 1);
CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_snapshot_key ON meeting_snapshots(meeting_date,venue,model_version);
