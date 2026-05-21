-- sticker_collector 统一建表/升级脚本
-- 新装数据库和旧版本升级都执行这一份。
-- 旧的 persona_sticker_asset 表已在 persona_mirror 升级脚本中 DROP，
-- 这里只创建新的全局表 sticker_asset / sticker_usage。

CREATE TABLE IF NOT EXISTS `sticker_asset` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `content_sha256` VARCHAR(64) NOT NULL COMMENT '文件内容SHA256',
  `content_md5` VARCHAR(32) NOT NULL COMMENT '文件内容MD5',
  `bucket_name` VARCHAR(128) NOT NULL COMMENT 'MinIO桶名',
  `object_name` VARCHAR(512) NOT NULL COMMENT 'MinIO对象路径',
  `content_type` VARCHAR(100) NULL COMMENT '内容类型',
  `file_ext` VARCHAR(16) NULL COMMENT '文件扩展名',
  `file_size` BIGINT NOT NULL DEFAULT 0 COMMENT '文件大小',
  `used_count` INT NOT NULL DEFAULT 1 COMMENT '全局累计出现次数',
  `recognize_status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'AI识别状态: pending/done/failed',
  `is_suitable_sticker` TINYINT(1) NULL COMMENT 'AI判断是否适合作为表情包',
  `sticker_meaning` TEXT NULL COMMENT 'AI给出的表情包含义',
  `emotion_tag` VARCHAR(32) NULL COMMENT 'AI给出的情绪标签(用于分桶)',
  `recognize_attempts` INT NOT NULL DEFAULT 0 COMMENT '累计识别尝试次数',
  `recognized_at` DATETIME(6) NULL COMMENT '识别完成时间',
  `recognize_error` TEXT NULL COMMENT '识别失败原因/原始返回',
  `source_url` TEXT NULL COMMENT '最近一次下载URL',
  `source_file` VARCHAR(512) NULL COMMENT 'OneBot原始file字段',
  `raw_segment_json` JSON NOT NULL COMMENT '最近一次原始消息分段',
  `first_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '首次出现',
  `last_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近出现',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sticker_asset_content_sha256` (`content_sha256`),
  KEY `idx_sticker_asset_content_md5` (`content_md5`),
  KEY `idx_sticker_asset_recognize_status` (`recognize_status`),
  KEY `idx_sticker_asset_emotion_tag` (`emotion_tag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全局表情包资产';

CREATE TABLE IF NOT EXISTS `sticker_usage` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `sticker_id` INT NOT NULL COMMENT 'sticker_asset.id 外键',
  `user_id` VARCHAR(32) NOT NULL COMMENT '发送者QQ',
  `used_count` INT NOT NULL DEFAULT 1 COMMENT '该用户使用次数',
  `last_group_id` VARCHAR(32) NULL COMMENT '最近发送群号',
  `last_sender_name` VARCHAR(100) NULL COMMENT '最近发送者展示名',
  `last_platform_message_id` VARCHAR(64) NULL COMMENT '最近平台消息ID',
  `first_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '首次使用时间',
  `last_seen_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近使用时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sticker_usage_sticker_user` (`sticker_id`, `user_id`),
  KEY `idx_sticker_usage_sticker_id` (`sticker_id`),
  KEY `idx_sticker_usage_user_id` (`user_id`),
  KEY `idx_sticker_usage_last_group_id` (`last_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='表情包使用记录(用户维度)';

-- 老库升级：新增 emotion_tag 列与索引（幂等）
DELIMITER $$

DROP PROCEDURE IF EXISTS `sticker_collector_sync_schema`$$
CREATE PROCEDURE `sticker_collector_sync_schema`()
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sticker_asset'
      AND COLUMN_NAME = 'emotion_tag'
  ) THEN
    ALTER TABLE `sticker_asset`
      ADD COLUMN `emotion_tag` VARCHAR(32) NULL COMMENT 'AI给出的情绪标签(用于分桶)' AFTER `sticker_meaning`;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sticker_asset'
      AND INDEX_NAME = 'idx_sticker_asset_emotion_tag'
  ) THEN
    ALTER TABLE `sticker_asset`
      ADD KEY `idx_sticker_asset_emotion_tag` (`emotion_tag`);
  END IF;
END$$

DELIMITER ;

CALL `sticker_collector_sync_schema`();
DROP PROCEDURE `sticker_collector_sync_schema`;
