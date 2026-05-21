from tortoise import fields
from tortoise.models import Model


class StickerAsset(Model):
    """全局表情包资产：一行 = 一张唯一图片（按 content_sha256 去重）。"""

    id = fields.IntField(pk=True, description="主键")
    content_sha256 = fields.CharField(max_length=64, unique=True, description="文件内容SHA256")
    content_md5 = fields.CharField(max_length=32, index=True, description="文件内容MD5")
    bucket_name = fields.CharField(max_length=128, description="MinIO桶名")
    object_name = fields.CharField(max_length=512, description="MinIO对象路径")
    content_type = fields.CharField(max_length=100, null=True, description="内容类型")
    file_ext = fields.CharField(max_length=16, null=True, description="文件扩展名")
    file_size = fields.BigIntField(default=0, description="文件大小")
    used_count = fields.IntField(default=1, description="全局累计出现次数")
    recognize_status = fields.CharField(
        max_length=16, default="pending", index=True, description="AI识别状态: pending/done/failed"
    )
    is_suitable_sticker = fields.BooleanField(null=True, description="AI判断是否适合作为表情包")
    sticker_meaning = fields.TextField(null=True, description="AI给出的表情包含义")
    recognize_attempts = fields.IntField(default=0, description="累计识别尝试次数")
    recognized_at = fields.DatetimeField(null=True, description="识别完成时间")
    recognize_error = fields.TextField(null=True, description="识别失败原因/原始返回")
    source_url = fields.TextField(null=True, description="最近一次下载URL")
    source_file = fields.CharField(max_length=512, null=True, description="OneBot原始file字段")
    raw_segment_json = fields.JSONField(default=dict, description="最近一次原始消息分段")
    first_seen_at = fields.DatetimeField(auto_now_add=True, description="首次出现")
    last_seen_at = fields.DatetimeField(auto_now=True, description="最近出现")

    class Meta:
        table = "sticker_asset"
        table_description = "全局表情包资产"


class StickerUsage(Model):
    """用户与表情包的使用关系：(sticker_id, user_id) 一行，记录某用户用过哪些表情包。"""

    id = fields.IntField(pk=True, description="主键")
    sticker_id = fields.IntField(index=True, description="sticker_asset.id 外键")
    user_id = fields.CharField(max_length=32, index=True, description="发送者QQ")
    used_count = fields.IntField(default=1, description="该用户使用次数")
    last_group_id = fields.CharField(max_length=32, null=True, index=True, description="最近发送群号")
    last_sender_name = fields.CharField(max_length=100, null=True, description="最近发送者展示名")
    last_platform_message_id = fields.CharField(max_length=64, null=True, description="最近平台消息ID")
    first_seen_at = fields.DatetimeField(auto_now_add=True, description="首次使用时间")
    last_seen_at = fields.DatetimeField(auto_now=True, description="最近使用时间")

    class Meta:
        table = "sticker_usage"
        table_description = "表情包使用记录(用户维度)"
        unique_together = (("sticker_id", "user_id"),)
