from tortoise import fields
from tortoise.models import Model


class TelegramCheckinBinding(Model):
    """一条 QQ 用户、Telegram 账号和目标签到机器人的绑定任务。"""

    id = fields.IntField(pk=True, description="主键")
    qq_user_id = fields.CharField(max_length=32, index=True, description="绑定人QQ")
    tg_api_id = fields.BigIntField(description="Telegram API ID")
    tg_api_hash = fields.CharField(max_length=128, description="Telegram API Hash")
    tg_session = fields.TextField(description="Telethon StringSession")
    tg_account_name = fields.CharField(max_length=100, description="Telegram账号备注")
    target_bot = fields.CharField(max_length=255, description="目标Telegram机器人用户名")
    checkin_command = fields.TextField(description="原样发送的签到指令")
    enabled = fields.BooleanField(default=True, index=True, description="是否启用")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "telegram_checkin_binding"
        table_description = "QQ用户与Telegram自动签到任务绑定"
        indexes = (("qq_user_id", "enabled"),)
