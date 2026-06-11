-- fund 插件建表脚本
-- 新装数据库执行这一份即可（项目无迁移工具，模型变更需在此手写升级语句）。

CREATE TABLE IF NOT EXISTS `fund_subscription` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` VARCHAR(32) NOT NULL COMMENT '绑定人QQ',
  `fund_code` VARCHAR(6) NOT NULL COMMENT '基金代码(6位)',
  `fund_name` VARCHAR(100) NULL COMMENT '基金名称(添加成功时回填,仅展示用)',
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '绑定时间',
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_fund_subscription_user_code` (`user_id`, `fund_code`),
  KEY `idx_fund_subscription_user_id` (`user_id`),
  KEY `idx_fund_subscription_fund_code` (`fund_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与基金的订阅绑定';
