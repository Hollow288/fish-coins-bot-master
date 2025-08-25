from tortoise import fields
from tortoise.models import Model

class EventNews(Model):
    """
    EventNews
    """
    news_id = fields.IntField(pk=True, description="ID")
    news_title = fields.CharField(max_length=200, null=True, description="活动标题")
    news_describe = fields.TextField(null=True, description="活动描述")
    news_img_url = fields.CharField(max_length=200, null=True, description="活动缩略图地址")
    news_start = fields.DatetimeField(null=True, description="活动开始时间")
    news_end = fields.DatetimeField(null=True, description="活动结束时间")
    del_flag = fields.CharField(max_length=1, default='0', null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "event_news"
        table_description = "活动咨询表"
