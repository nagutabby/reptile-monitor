CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    temp_c REAL NOT NULL,
    humidity REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_readings_recorded_at ON readings (recorded_at);

CREATE TABLE IF NOT EXISTS alert_state (
    id INTEGER PRIMARY KEY,
    is_abnormal INTEGER NOT NULL DEFAULT 0,
    last_alert_at TEXT
);

INSERT OR IGNORE INTO alert_state (id, is_abnormal, last_alert_at) VALUES (1, 0, NULL);
