-- persona_mirror 统一建表/升级脚本
-- 新装数据库和旧版本升级都执行这一份。

CREATE TABLE IF NOT EXISTS `persona_target` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `owner_user_id` VARCHAR(32) NOT NULL COMMENT '绑定该目标的管理员QQ',
  `target_user_id` VARCHAR(32) NOT NULL COMMENT '被观察目标QQ',
  `target_name` VARCHAR(100) NULL COMMENT '目标备注名',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用采集',
  `auto_reply_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用自动模仿回复',
  `trigger_keywords_json` JSON NOT NULL COMMENT '自动触发关键词',
  `summary_batch_size` INT NOT NULL DEFAULT 30 COMMENT '触发总结的增量条数',
  `last_summarized_message_id` INT NOT NULL DEFAULT 0 COMMENT '已总结到的消息ID',
  `last_auto_reply_at` DATETIME(6) NULL COMMENT '最近自动回复时间',
  `total_collected_messages` INT NOT NULL DEFAULT 0 COMMENT '累计采集条数',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_persona_target_target_user_id` (`target_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人设模仿目标';

CREATE TABLE IF NOT EXISTS `persona_message` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `target_user_id` VARCHAR(32) NOT NULL COMMENT '目标QQ',
  `group_id` VARCHAR(32) NULL COMMENT '群号',
  `chat_type` VARCHAR(16) NOT NULL COMMENT '群聊/私聊',
  `platform_message_id` VARCHAR(64) NULL COMMENT '平台消息ID',
  `plain_text` TEXT NULL COMMENT '纯文本',
  `normalized_text` TEXT NULL COMMENT '归一化后的文本',
  `raw_segments_json` JSON NOT NULL COMMENT '原始消息分段',
  `feature_json` JSON NOT NULL COMMENT '局部统计特征',
  `message_time` DATETIME(6) NOT NULL COMMENT '消息时间',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '入库时间',
  PRIMARY KEY (`id`),
  KEY `idx_persona_message_target_user_id` (`target_user_id`),
  KEY `idx_persona_message_message_time` (`message_time`),
  KEY `idx_persona_message_target_user_id_message_time` (`target_user_id`, `message_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人设原始消息';

CREATE TABLE IF NOT EXISTS `persona_asset` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `target_user_id` VARCHAR(32) NOT NULL COMMENT '目标QQ',
  `message_ref_id` INT NULL COMMENT '来源消息ID',
  `asset_type` VARCHAR(16) NOT NULL COMMENT '固定为face',
  `asset_key` VARCHAR(255) NOT NULL COMMENT '去重主键',
  `face_id` VARCHAR(32) NOT NULL COMMENT 'QQ表情ID',
  `used_count` INT NOT NULL DEFAULT 1 COMMENT '出现次数',
  `first_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '首次出现',
  `last_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近出现',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_persona_asset_target_type_key` (`target_user_id`, `asset_type`, `asset_key`),
  KEY `idx_persona_asset_target_user_id` (`target_user_id`),
  KEY `idx_persona_asset_asset_type` (`asset_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人设QQ表情使用记录';

CREATE TABLE IF NOT EXISTS `persona_profile_state` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `target_user_id` VARCHAR(32) NOT NULL COMMENT '目标QQ',
  `current_profile_json` JSON NOT NULL COMMENT '当前聚合画像',
  `latest_snapshot_id` INT NULL COMMENT '最近快照ID',
  `last_summary_message_id` INT NOT NULL DEFAULT 0 COMMENT '最近总结到的消息ID',
  `last_summary_at` DATETIME(6) NULL COMMENT '最近总结时间',
  `total_message_count` INT NOT NULL DEFAULT 0 COMMENT '画像基于的消息总量',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_persona_profile_state_target_user_id` (`target_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人设聚合画像';

CREATE TABLE IF NOT EXISTS `persona_profile_snapshot` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `target_user_id` VARCHAR(32) NOT NULL COMMENT '目标QQ',
  `summary_type` VARCHAR(32) NOT NULL DEFAULT 'incremental' COMMENT '总结类型',
  `source_message_count` INT NOT NULL DEFAULT 0 COMMENT '本次参与总结的消息数',
  `start_message_id` INT NOT NULL DEFAULT 0 COMMENT '起始消息ID',
  `end_message_id` INT NOT NULL DEFAULT 0 COMMENT '结束消息ID',
  `summary_json` JSON NOT NULL COMMENT '本次画像JSON',
  `prompt_text` LONGTEXT NULL COMMENT '总结时使用的提示词',
  `raw_response` LONGTEXT NULL COMMENT 'AI原始返回',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_persona_profile_snapshot_target_user_id` (`target_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人设画像快照';

DELIMITER $$

DROP PROCEDURE IF EXISTS `persona_mirror_sync_schema`$$
CREATE PROCEDURE `persona_mirror_sync_schema`()
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_target'
      AND COLUMN_NAME = 'auto_reply_enabled'
  ) THEN
    ALTER TABLE `persona_target`
      ADD COLUMN `auto_reply_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用自动模仿回复' AFTER `enabled`;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_target'
      AND COLUMN_NAME = 'trigger_keywords_json'
  ) THEN
    ALTER TABLE `persona_target`
      ADD COLUMN `trigger_keywords_json` JSON NULL COMMENT '自动触发关键词' AFTER `auto_reply_enabled`;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_target'
      AND COLUMN_NAME = 'last_auto_reply_at'
  ) THEN
    ALTER TABLE `persona_target`
      ADD COLUMN `last_auto_reply_at` DATETIME(6) NULL COMMENT '最近自动回复时间' AFTER `last_summarized_message_id`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'file_unique'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `file_unique`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'file_name'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `file_name`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'mime_type'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `mime_type`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'remote_url'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `remote_url`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'local_path'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `local_path`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'asset_hash'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `asset_hash`;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'persona_asset'
      AND COLUMN_NAME = 'tags_json'
  ) THEN
    ALTER TABLE `persona_asset` DROP COLUMN `tags_json`;
  END IF;
END$$

DELIMITER ;

CALL `persona_mirror_sync_schema`();
DROP PROCEDURE `persona_mirror_sync_schema`;

UPDATE `persona_target`
SET `trigger_keywords_json` = JSON_ARRAY(`target_name`)
WHERE (`trigger_keywords_json` IS NULL OR JSON_LENGTH(`trigger_keywords_json`) = 0)
  AND `target_name` IS NOT NULL
  AND `target_name` <> '';

UPDATE `persona_target`
SET `trigger_keywords_json` = JSON_ARRAY()
WHERE `trigger_keywords_json` IS NULL;

ALTER TABLE `persona_target`
  MODIFY COLUMN `auto_reply_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用自动模仿回复',
  MODIFY COLUMN `trigger_keywords_json` JSON NOT NULL COMMENT '自动触发关键词',
  MODIFY COLUMN `last_auto_reply_at` DATETIME(6) NULL COMMENT '最近自动回复时间';

DELETE FROM `persona_asset`
WHERE `asset_type` = 'image';

DELETE FROM `persona_asset`
WHERE `face_id` IS NULL OR `face_id` = '';

ALTER TABLE `persona_asset`
  MODIFY COLUMN `asset_type` VARCHAR(16) NOT NULL COMMENT '固定为face',
  MODIFY COLUMN `face_id` VARCHAR(32) NOT NULL COMMENT 'QQ表情ID';
