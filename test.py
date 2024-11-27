import asyncio
from fish_coins_bot.utils.image_utils import fetch_image
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import httpx

async def test_fetch_image():
    live_cover_url = "https://i0.hdslb.com/bfs/live/new_room_cover/90d1125ffdf5a51549404aa88a52ebb624b6b59c.jpg"
    live_avatar_url = "https://i1.hdslb.com/bfs/face/463cab30630a0230e997625c07aa1213b19905b2.jpg"
    icon_path = "fish_coins_bot/img/icon.png"

    # 获取背景图片
    background_image = await fetch_image(live_cover_url)

    # 调整背景图片尺寸到 640x360
    target_size = (640, 360)
    resized_background = background_image.resize(target_size, Image.Resampling.LANCZOS)

    # 步骤 1: 应用高斯模糊
    blurred_background = resized_background.filter(ImageFilter.GaussianBlur(2))  # 模糊半径为 10

    # 步骤 2: 制造颗粒感（降低分辨率再放大）
    small = blurred_background.resize(
        (blurred_background.size[0], blurred_background.size[1]),
        resample=Image.NEAREST
    )
    frosted_glass_background = small.resize(blurred_background.size, Image.NEAREST)

    # 步骤 3: 添加半透明黑色遮罩 (RGBA)
    overlay = Image.new("RGBA", frosted_glass_background.size, (0, 0, 0, 100))  # 黑色遮罩，透明度 100

    # 步骤 4: 合成磨砂玻璃背景和遮罩
    background_with_overlay = Image.alpha_composite(frosted_glass_background.convert("RGBA"), overlay)

    # 获取头像图片
    avatar_image = await fetch_image(live_avatar_url)

    # 调整头像图片尺寸到 100x100
    avatar_size = (100, 100)
    resized_avatar = avatar_image.resize(avatar_size, Image.Resampling.LANCZOS)

    # 创建圆形头像蒙版
    mask = Image.new("L", avatar_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)

    # 将圆形蒙版应用到头像
    rounded_avatar = Image.new("RGBA", avatar_size, (255, 255, 255, 0))
    rounded_avatar.paste(resized_avatar, (0, 0), mask)

    # 创建阴影
    shadow = Image.new("RGBA", (avatar_size[0] + 10, avatar_size[1] + 10), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((5, 5, avatar_size[0] + 5, avatar_size[1] + 5), fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))

    # 加载字体
    font_path = "fish_coins_bot/fonts/ZCOOLKuaiLe-Regular.ttf"
    font_path_kbl = "fish_coins_bot/fonts/日出而作日落想你.ttf"

    # 修改文字内容
    live_name = "喵不动了喵"
    live_address = "https://live.bilibili.com/3786110"
    live_title = "《！州一下 可扶贫》"
    live_icon_text = "开播啦!"

    # 设置字体大小
    main_font_size = avatar_size[1] * 0.7
    main_font = ImageFont.truetype(font_path, size=int(main_font_size))
    small_font_size = avatar_size[1] * 0.3
    small_font = ImageFont.truetype(font_path, size=int(small_font_size))
    title_font_size = 30
    title_font = ImageFont.truetype(font_path, size=title_font_size)
    icon_text_font_size = 100
    icon_text_font = ImageFont.truetype(font_path_kbl, size=icon_text_font_size)

    # 加载图标并调整大小
    icon_image = Image.open(icon_path)
    icon_size = (150, 150)
    resized_icon = icon_image.resize(icon_size, Image.Resampling.LANCZOS)

    # 计算主文字和小文字的总高度
    main_bbox = main_font.getbbox(live_name)
    main_text_height = main_bbox[3] - main_bbox[1]

    small_bbox = small_font.getbbox(live_address)
    small_text_height = small_bbox[3] - small_bbox[1]

    total_text_height = main_text_height + small_text_height + 10

    # 计算标题文字高度
    title_bbox = title_font.getbbox(live_title)
    title_text_height = title_bbox[3] - title_bbox[1]

    # 设置布局
    layout_top = 20
    icon_position_top = layout_top + total_text_height + 30

    # 绘制头像
    avatar_position = (target_size[0] - avatar_size[0] - 20, layout_top + (total_text_height - avatar_size[1]) // 2)
    background_with_overlay.paste(shadow, (avatar_position[0] - 5, avatar_position[1] - 5), shadow)
    background_with_overlay.paste(rounded_avatar, avatar_position, rounded_avatar)

    # 设置主文字和小文字
    main_text_position = (avatar_position[0] - main_bbox[2] - 20, layout_top)
    small_text_position = (main_text_position[0] + main_bbox[2] - small_bbox[2], main_text_position[1] + main_text_height + 10)

    draw = ImageDraw.Draw(background_with_overlay)
    draw.text(main_text_position, live_name, font=main_font, fill=(255, 255, 255))
    draw.text(small_text_position, live_address, font=small_font, fill=(255, 255, 255), underline=True)

    # 绘制图标和附加文字
    icon_position = ((target_size[0] - icon_size[0]) // 2 - 180, icon_position_top)
    icon_text_position = (icon_position[0] + icon_size[0] + 10, icon_position[1] + (icon_size[1] - icon_text_font_size) // 2 - 12)
    background_with_overlay.paste(resized_icon, icon_position, resized_icon)
    draw.text(icon_text_position, live_icon_text, font=icon_text_font, fill=(255, 192, 203))

    # 绘制标题
    title_position = ((target_size[0] - title_bbox[2]) // 2, target_size[1] - title_text_height - 20)
    draw.text(title_position, live_title, font=title_font, fill=(255, 255, 255))

    # 显示和保存最终图片
    background_with_overlay.show()
    background_with_overlay.save("final_image_with_icon.png")
    print("Final image saved as final_image_with_icon.png.")





if __name__ == "__main__":
    asyncio.run(test_fetch_image())
