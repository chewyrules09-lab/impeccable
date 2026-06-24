-- Every signal (taken AND skipped), every order, every fill, and every risk
-- rule trigger gets a row here. This is the audit trail the README promises.

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL,
    stop REAL,
    target REAL,
    size INTEGER,
    confidence REAL,
    rules_fired_json TEXT NOT NULL DEFAULT '[]',
    rules_failed_json TEXT NOT NULL DEFAULT '[]',
    taken INTEGER NOT NULL DEFAULT 0,
    skip_reason TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    client_order_id TEXT PRIMARY KEY,
    ts_created TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    limit_price REAL,
    reference_price REAL NOT NULL,
    time_in_force TEXT NOT NULL,
    instrument_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT NOT NULL REFERENCES orders(client_order_id),
    ts TEXT NOT NULL,
    fill_price REAL NOT NULL,
    fill_qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    rule TEXT NOT NULL,
    client_order_id TEXT,
    action TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    daily_realized_pnl REAL NOT NULL,
    trades_today INTEGER NOT NULL,
    mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    killed INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT
);
