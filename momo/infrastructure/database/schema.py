"""SQLite database schema for wardriving data."""

WARDRIVING_SCHEMA = """
-- ============================================
-- MoMo Wardriving Database Schema
-- Version: 1.0.0
-- Compatible with: Kismet, Wigle.net export
-- ============================================

-- Access Points table (unique by BSSID)
CREATE TABLE IF NOT EXISTS access_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bssid TEXT NOT NULL UNIQUE,
    ssid TEXT DEFAULT '<hidden>',
    channel INTEGER NOT NULL DEFAULT 0,
    frequency INTEGER DEFAULT 0,
    encryption TEXT DEFAULT 'open',
    wps_enabled INTEGER DEFAULT 0,
    vendor TEXT,
    
    -- Timestamps
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    
    -- Best signal location (where RSSI was strongest)
    best_rssi INTEGER DEFAULT -100,
    best_lat REAL,
    best_lon REAL,
    best_alt REAL,
    
    -- Metadata
    clients_seen INTEGER DEFAULT 0,
    probes_targeting INTEGER DEFAULT 0,
    
    -- Capture status
    handshake_captured INTEGER DEFAULT 0,
    handshake_path TEXT,
    password_cracked INTEGER DEFAULT 0,
    cracked_password TEXT,
    cracked_at TEXT,
    
    -- Notes
    notes TEXT
);

-- AP Observations (each time an AP is seen)
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ap_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    rssi INTEGER NOT NULL,
    latitude REAL,
    longitude REAL,
    altitude REAL,
    
    FOREIGN KEY (ap_id) REFERENCES access_points(id) ON DELETE CASCADE
);

-- Scan Sessions (wardriving sessions)
CREATE TABLE IF NOT EXISTS scan_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    interface TEXT,
    channels TEXT,  -- JSON array: [1, 6, 11]
    
    -- Stats
    aps_found INTEGER DEFAULT 0,
    aps_new INTEGER DEFAULT 0,
    observations_count INTEGER DEFAULT 0,
    probes_captured INTEGER DEFAULT 0,
    
    -- Track
    distance_km REAL DEFAULT 0,
    gpx_path TEXT,
    
    -- Environment
    device_name TEXT DEFAULT 'MoMo',
    notes TEXT
);

-- Probe Requests (client device tracking)
CREATE TABLE IF NOT EXISTS probe_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_mac TEXT NOT NULL,
    ssid_probed TEXT,
    timestamp TEXT NOT NULL,
    rssi INTEGER,
    latitude REAL,
    longitude REAL,
    vendor TEXT,
    
    -- Link to targeting AP if exists
    target_ap_id INTEGER,
    
    FOREIGN KEY (target_ap_id) REFERENCES access_points(id) ON DELETE SET NULL
);

-- GPS Track points (for GPX export)
CREATE TABLE IF NOT EXISTS track_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL,
    speed REAL,
    heading REAL,
    satellites INTEGER,
    hdop REAL,
    
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id) ON DELETE CASCADE
);

-- OUI Vendor lookup cache
CREATE TABLE IF NOT EXISTS oui_cache (
    mac_prefix TEXT PRIMARY KEY,  -- First 6 chars: AA:BB:CC
    vendor TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================
-- Indexes for performance
-- ============================================

CREATE INDEX IF NOT EXISTS idx_ap_bssid ON access_points(bssid);
CREATE INDEX IF NOT EXISTS idx_ap_ssid ON access_points(ssid);
CREATE INDEX IF NOT EXISTS idx_ap_encryption ON access_points(encryption);
CREATE INDEX IF NOT EXISTS idx_ap_channel ON access_points(channel);
CREATE INDEX IF NOT EXISTS idx_ap_handshake ON access_points(handshake_captured);

CREATE INDEX IF NOT EXISTS idx_obs_ap ON observations(ap_id);
CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp);
CREATE INDEX IF NOT EXISTS idx_obs_location ON observations(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_probe_mac ON probe_requests(client_mac);
CREATE INDEX IF NOT EXISTS idx_probe_ssid ON probe_requests(ssid_probed);
CREATE INDEX IF NOT EXISTS idx_probe_timestamp ON probe_requests(timestamp);

CREATE INDEX IF NOT EXISTS idx_track_session ON track_points(session_id);
CREATE INDEX IF NOT EXISTS idx_track_timestamp ON track_points(timestamp);

-- ============================================
-- Views for common queries
-- ============================================

-- AP summary with observation count
CREATE VIEW IF NOT EXISTS v_ap_summary AS
SELECT 
    ap.id,
    ap.bssid,
    ap.ssid,
    ap.channel,
    ap.encryption,
    ap.best_rssi,
    ap.best_lat,
    ap.best_lon,
    ap.handshake_captured,
    ap.password_cracked,
    COUNT(o.id) as observation_count,
    ap.first_seen,
    ap.last_seen
FROM access_points ap
LEFT JOIN observations o ON o.ap_id = ap.id
GROUP BY ap.id
ORDER BY ap.last_seen DESC;

-- Recent APs (last 24 hours)
CREATE VIEW IF NOT EXISTS v_recent_aps AS
SELECT * FROM v_ap_summary
WHERE datetime(last_seen) > datetime('now', '-24 hours')
ORDER BY last_seen DESC;

-- Crackable APs (with handshake, not cracked)
CREATE VIEW IF NOT EXISTS v_crackable AS
SELECT * FROM access_points
WHERE handshake_captured = 1 
  AND password_cracked = 0
ORDER BY best_rssi DESC;

-- Client device summary
CREATE VIEW IF NOT EXISTS v_client_summary AS
SELECT 
    client_mac,
    vendor,
    COUNT(DISTINCT ssid_probed) as networks_probed,
    COUNT(*) as probe_count,
    MIN(timestamp) as first_seen,
    MAX(timestamp) as last_seen
FROM probe_requests
GROUP BY client_mac
ORDER BY probe_count DESC;

-- Session stats
CREATE VIEW IF NOT EXISTS v_session_stats AS
SELECT 
    s.scan_id,
    s.started_at,
    s.ended_at,
    s.aps_found,
    s.aps_new,
    s.distance_km,
    COUNT(t.id) as track_points,
    ROUND((julianday(COALESCE(s.ended_at, datetime('now'))) - julianday(s.started_at)) * 24 * 60, 1) as duration_minutes
FROM scan_sessions s
LEFT JOIN track_points t ON t.session_id = s.id
GROUP BY s.id
ORDER BY s.started_at DESC;
"""

