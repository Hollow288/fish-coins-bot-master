CREATE TABLE IF NOT EXISTS `telegram_checkin_binding` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `qq_user_id` VARCHAR(32) NOT NULL COMMENT '绑定人QQ',
    `tg_api_id` BIGINT NOT NULL COMMENT 'Telegram API ID',
    `tg_api_hash` VARCHAR(128) NOT NULL COMMENT 'Telegram API Hash',
    `tg_session` TEXT NOT NULL COMMENT 'Telethon StringSession',
    `tg_account_name` VARCHAR(100) NOT NULL COMMENT 'Telegram账号备注',
    `target_bot` VARCHAR(255) NOT NULL COMMENT '目标Telegram机器人用户名',
    `checkin_command` TEXT NOT NULL COMMENT '原样发送的签到指令',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_tg_checkin_qq_user_id` (`qq_user_id`),
    INDEX `idx_tg_checkin_enabled` (`enabled`),
    INDEX `idx_tg_checkin_qq_enabled` (`qq_user_id`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='QQ用户与Telegram自动签到任务绑定';
