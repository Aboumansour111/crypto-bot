CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY,
    exchange TEXT NOT NULL,
    exchange_market_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    base_symbol TEXT NOT NULL,
    quote_symbol TEXT NOT NULL,
    status TEXT,
    tradable INTEGER NOT NULL DEFAULT 0,
    suspended INTEGER NOT NULL DEFAULT 0,
    otc_tradable INTEGER NOT NULL DEFAULT 0,
    coming_soon INTEGER NOT NULL DEFAULT 0,
    price REAL,
    volume_24h REAL,
    price_increment REAL,
    price_precision INTEGER,
    quantity_precision INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, exchange_market_id)
);

CREATE INDEX IF NOT EXISTS idx_markets_quote
ON markets(quote_symbol);

CREATE INDEX IF NOT EXISTS idx_markets_active
ON markets(tradable, suspended, coming_soon);

CREATE TABLE IF NOT EXISTS ohlcv (
    id INTEGER PRIMARY KEY,
    market_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    quote_volume REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(market_id) REFERENCES markets(id),
    UNIQUE(market_id, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_market_tf_ts
ON ohlcv(market_id, timeframe, timestamp);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    job TEXT NOT NULL,
    status TEXT NOT NULL,
    rows_written INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY,
    market_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,

    sma_20 REAL,
    sma_50 REAL,
    sma_200 REAL,

    ema_20 REAL,
    ema_50 REAL,
    ema_200 REAL,

    rsi_14 REAL,

    roc_7 REAL,
    roc_14 REAL,
    roc_30 REAL,

    atr_14 REAL,
    atr_pct_14 REAL,

    return_1 REAL,
    return_7 REAL,
    return_14 REAL,
    return_30 REAL,

    volume_sma_20 REAL,
    volume_ratio_20 REAL,

    realized_vol_20 REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(market_id) REFERENCES markets(id),

    UNIQUE(market_id, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_features_market_tf_ts
ON features(market_id, timeframe, timestamp);

CREATE INDEX IF NOT EXISTS idx_features_tf_ts
ON features(timeframe, timestamp);

CREATE TABLE IF NOT EXISTS market_context (
    id INTEGER PRIMARY KEY,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,

    btc_close REAL,
    btc_return_1 REAL,
    btc_return_7 REAL,
    btc_return_30 REAL,

    btc_sma_20 REAL,
    btc_sma_50 REAL,
    btc_sma_200 REAL,
    btc_rsi_14 REAL,
    btc_atr_pct_14 REAL,
    btc_realized_vol_20 REAL,

    total_markets INTEGER NOT NULL DEFAULT 0,
    bullish_markets INTEGER NOT NULL DEFAULT 0,
    bearish_markets INTEGER NOT NULL DEFAULT 0,
    neutral_markets INTEGER NOT NULL DEFAULT 0,

    breadth_sma20 REAL,
    breadth_sma50 REAL,
    breadth_positive_7d REAL,
    breadth_positive_30d REAL,

    avg_volume_ratio_20 REAL,
    avg_realized_vol_20 REAL,
    avg_atr_pct_14 REAL,

    market_regime TEXT NOT NULL DEFAULT 'NEUTRAL',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_context_tf_ts
ON market_context(timeframe, timestamp);


CREATE TABLE IF NOT EXISTS strategy_scores (
    id INTEGER PRIMARY KEY,
    market_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,

    trend_score REAL,
    momentum_score REAL,
    volume_score REAL,
    volatility_score REAL,
    liquidity_score REAL,
    market_context_score REAL,

    total_score REAL,
    candidate INTEGER NOT NULL DEFAULT 0,

    strategy_version TEXT NOT NULL DEFAULT 'S1_BASE',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(market_id) REFERENCES markets(id),

    UNIQUE(market_id, timeframe, timestamp, strategy_version)
);

CREATE INDEX IF NOT EXISTS idx_strategy_scores_tf_ts
ON strategy_scores(timeframe, timestamp);

CREATE INDEX IF NOT EXISTS idx_strategy_scores_candidates
ON strategy_scores(timeframe, timestamp, candidate);


CREATE TABLE IF NOT EXISTS rankings (
    id INTEGER PRIMARY KEY,
    market_id INTEGER NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,

    strategy_version TEXT NOT NULL,
    total_score REAL NOT NULL,

    rank INTEGER NOT NULL,
    percentile REAL,

    selected INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(market_id) REFERENCES markets(id),

    UNIQUE(
        market_id,
        timeframe,
        timestamp,
        strategy_version
    )
);

CREATE INDEX IF NOT EXISTS idx_rankings_tf_ts_rank
ON rankings(timeframe, timestamp, rank);

CREATE INDEX IF NOT EXISTS idx_rankings_selected
ON rankings(timeframe, timestamp, selected);
