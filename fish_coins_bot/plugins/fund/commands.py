"""基金指令：添加基金 / 删除基金 / 基金走势。

- 添加基金 270042：绑定发送人 QQ 与基金，并调服务端写接口开始监控（慢，先回提示）。
- 删除基金 270042：仅解除本地绑定，不取消服务端监控（他人可能仍绑定，速览图也要展示）。
- 基金走势：按发送人绑定的基金出详细点评长图（走势曲线 + AI 点评）。
群聊/私聊均可用，回复跟随来源会话。
"""
import re

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.exception import MatcherException
from nonebot.log import logger
from nonebot.params import CommandArg

from .config import get_plugin_config
from .models import FundSubscription
from .services.api_service import add_fund
from .services.push_service import collect_detail_items
from .services.render_service import render_report

_CODE_PATTERN = re.compile(r"^\d{6}$")

add_fund_cmd = on_command("添加基金", priority=10, block=True)
remove_fund_cmd = on_command("删除基金", aliases={"取消基金"}, priority=10, block=True)
my_funds_cmd = on_command("基金走势", aliases={"我的基金"}, priority=10, block=True)


@add_fund_cmd.handle()
async def add_fund_handle(event: MessageEvent, args: Message = CommandArg()):
    code = args.extract_plain_text().strip()
    if not _CODE_PATTERN.match(code):
        await add_fund_cmd.finish("请输入 6 位基金代码，例如：添加基金 270042")

    user_id = str(event.user_id)
    if await FundSubscription.filter(user_id=user_id, fund_code=code).exists():
        await add_fund_cmd.finish(f"你已经添加过基金 {code} ，发送「基金走势」即可查看。")

    # await add_fund_cmd.send(f"正在添加基金 {code}，服务端需要回补历史数据，可能要十几秒，请稍候…")

    body = await add_fund(code)
    if body is None:
        await add_fund_cmd.finish("基金服务暂时不可用，请稍后再试。")
    if body.get("code") != 200:
        await add_fund_cmd.finish(f"添加失败：{body.get('msg') or '未知错误'}")

    data = body.get("data") or {}
    fund_name = data.get("fundName") if isinstance(data, dict) else None
    try:
        await FundSubscription.get_or_create(
            user_id=user_id, fund_code=code, defaults={"fund_name": fund_name}
        )
    except MatcherException:
        raise
    except Exception as exc:
        logger.error(f"[fund] 绑定 {user_id} - {code} 入库失败: {exc}")
        await add_fund_cmd.finish("添加失败（绑定入库异常），请稍后再试。")

    display = f"{fund_name}（{code}）" if fund_name else code
    await add_fund_cmd.finish(f"添加成功：{display}，已开始监控。发送「基金走势」查看详情。")


@remove_fund_cmd.handle()
async def remove_fund_handle(event: MessageEvent, args: Message = CommandArg()):
    code = args.extract_plain_text().strip()
    if not _CODE_PATTERN.match(code):
        await remove_fund_cmd.finish("请输入 6 位基金代码，例如：删除基金 270042")

    user_id = str(event.user_id)
    deleted = await FundSubscription.filter(user_id=user_id, fund_code=code).delete()
    if not deleted:
        await remove_fund_cmd.finish(f"你没有绑定基金 {code}，无需删除。")
    await remove_fund_cmd.finish(f"已解除你与基金 {code} 的绑定。")


@my_funds_cmd.handle()
async def my_funds_handle(event: MessageEvent):
    user_id = str(event.user_id)
    codes = await FundSubscription.filter(user_id=user_id).order_by("created_at").values_list(
        "fund_code", flat=True
    )
    if not codes:
        await my_funds_cmd.finish("你还没有绑定任何基金，先发送「添加基金 270042」添加一只吧。")

    await my_funds_cmd.send(
        f"正在生成你绑定的 {len(codes)} 只基金的走势点评图，AI 点评 + 出图约需几十秒，请稍候…"
    )

    try:
        config = get_plugin_config()
        items = await collect_detail_items(list(codes), config)
        if not items:
            await my_funds_cmd.finish("基金数据获取失败（服务端不可用或基金未在监控），请稍后再试。")

        image_bytes = await render_report(items)
        if not image_bytes:
            logger.error(f"[fund] 用户 {user_id} 基金走势渲染失败。")
            await my_funds_cmd.finish("渲染基金走势图失败，请联系管理员。")
    except MatcherException:
        raise
    except Exception as exc:
        logger.error(f"[fund] 用户 {user_id} 基金走势指令异常: {exc}")
        await my_funds_cmd.finish("生成基金走势图出错了，请稍后再试。")

    await my_funds_cmd.finish(MessageSegment.image(image_bytes))
