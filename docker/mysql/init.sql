-- ═══════════════════════════════════════════════════════════════════════════
-- PeerLearn — MySQL Initialization Script
-- Runs once when the MySQL container is first created.
-- The database itself is already created by MYSQL_DATABASE env var.
-- This script applies additional configuration.
-- ═══════════════════════════════════════════════════════════════════════════

-- Ensure the database uses the correct character set
ALTER DATABASE peer_learning
  CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- Grant all privileges to the application user (already created by Docker env)
-- This is a safety net in case the env-var user creation was partial.
GRANT ALL PRIVILEGES ON peer_learning.* TO 'peerlearn'@'%';
FLUSH PRIVILEGES;

-- ── Performance tuning (applies to this session for verification) ────────────
-- Full configuration is set via --command flags in docker-compose.yml
SET GLOBAL innodb_buffer_pool_size = 268435456;   -- 256 MB
