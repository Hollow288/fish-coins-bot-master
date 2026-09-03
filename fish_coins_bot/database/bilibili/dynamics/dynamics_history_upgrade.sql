-- Run once when upgrading an existing database.
-- Existing rows are treated as bilibili history.

ALTER TABLE dynamics_history
    ADD COLUMN platform VARCHAR(32) NOT NULL DEFAULT 'bilibili' COMMENT '平台' AFTER id;

ALTER TABLE dynamics_history
    ADD COLUMN created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间' AFTER id_str;

CREATE INDEX idx_dynamics_history_platform_uid_id
    ON dynamics_history (platform, uid, id_str);
