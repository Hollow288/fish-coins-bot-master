from tortoise import fields
from tortoise.models import Model


class PersonaTarget(Model):
    id = fields.IntField(pk=True, description="主键")
    owner_user_id = fields.CharField(max_length=32, description="绑定该目标的管理员QQ")
    target_user_id = fields.CharField(max_length=32, unique=True, description="被观察目标QQ")
    target_name = fields.CharField(max_length=100, null=True, description="目标备注名")
    enabled = fields.BooleanField(default=True, description="是否启用采集")
    auto_reply_enabled = fields.BooleanField(default=True, description="是否启用自动模仿回复")
    trigger_keywords_json = fields.JSONField(default=list, description="自动触发关键词")
    summary_batch_size = fields.IntField(default=30, description="触发总结的增量条数")
    last_summarized_message_id = fields.IntField(default=0, description="已总结到的消息ID")
    last_auto_reply_at = fields.DatetimeField(null=True, description="最近自动回复时间")
    total_collected_messages = fields.IntField(default=0, description="累计采集条数")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "persona_target"
        table_description = "人设模仿目标"


class PersonaMessage(Model):
    id = fields.IntField(pk=True, description="主键")
    target_user_id = fields.CharField(max_length=32, index=True, description="目标QQ")
    group_id = fields.CharField(max_length=32, null=True, description="群号")
    chat_type = fields.CharField(max_length=16, description="群聊/私聊")
    platform_message_id = fields.CharField(max_length=64, null=True, description="平台消息ID")
    plain_text = fields.TextField(null=True, description="纯文本")
    normalized_text = fields.TextField(null=True, description="归一化后的文本")
    raw_segments_json = fields.JSONField(default=list, description="原始消息分段")
    feature_json = fields.JSONField(default=dict, description="局部统计特征")
    scene_type = fields.CharField(max_length=32, default="主动发言", description="场景分类")
    reply_to_text = fields.TextField(null=True, description="被回复消息的文本")
    reply_to_user_name = fields.CharField(max_length=100, null=True, description="被回复者名称")
    is_continuation = fields.BooleanField(default=False, description="是否为连续发言")
    context_json = fields.JSONField(default=list, description="发言前群聊上下文")
    message_time = fields.DatetimeField(index=True, description="消息时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="入库时间")

    class Meta:
        table = "persona_message"
        table_description = "人设原始消息"
        indexes = (("target_user_id", "message_time"),)


class PersonaAsset(Model):
    id = fields.IntField(pk=True, description="主键")
    target_user_id = fields.CharField(max_length=32, index=True, description="目标QQ")
    message_ref_id = fields.IntField(null=True, description="来源消息ID")
    asset_type = fields.CharField(max_length=16, index=True, description="固定为face")
    asset_key = fields.CharField(max_length=255, description="去重主键")
    face_id = fields.CharField(max_length=32, description="QQ表情ID")
    used_count = fields.IntField(default=1, description="出现次数")
    first_seen_at = fields.DatetimeField(auto_now_add=True, description="首次出现")
    last_seen_at = fields.DatetimeField(auto_now=True, description="最近出现")

    class Meta:
        table = "persona_asset"
        table_description = "人设QQ表情使用记录"
        unique_together = (("target_user_id", "asset_type", "asset_key"),)


class PersonaProfileState(Model):
    id = fields.IntField(pk=True, description="主键")
    target_user_id = fields.CharField(max_length=32, unique=True, description="目标QQ")
    current_profile_json = fields.JSONField(default=dict, description="当前聚合画像")
    latest_snapshot_id = fields.IntField(null=True, description="最近快照ID")
    last_summary_message_id = fields.IntField(default=0, description="最近总结到的消息ID")
    last_summary_at = fields.DatetimeField(null=True, description="最近总结时间")
    total_message_count = fields.IntField(default=0, description="画像基于的消息总量")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "persona_profile_state"
        table_description = "人设聚合画像"


class PersonaProfileSnapshot(Model):
    id = fields.IntField(pk=True, description="主键")
    target_user_id = fields.CharField(max_length=32, index=True, description="目标QQ")
    summary_type = fields.CharField(max_length=32, default="incremental", description="总结类型")
    source_message_count = fields.IntField(default=0, description="本次参与总结的消息数")
    start_message_id = fields.IntField(default=0, description="起始消息ID")
    end_message_id = fields.IntField(default=0, description="结束消息ID")
    summary_json = fields.JSONField(default=dict, description="本次画像JSON")
    prompt_text = fields.TextField(null=True, description="总结时使用的提示词")
    raw_response = fields.TextField(null=True, description="AI原始返回")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "persona_profile_snapshot"
        table_description = "人设画像快照"
