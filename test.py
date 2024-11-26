import asyncio
from fish_coins_bot.utils.image_utils import fetch_image
from PIL import Image, ImageDraw, ImageFilter, ImageFont


async def test_fetch_image():
    live_cover_url = "https://i0.hdslb.com/bfs/live/2388faed3728f3396052273ad4c3c9af21c411fc.jpg"
    live_avatar_url = "https://i1.hdslb.com/bfs/face/463cab30630a0230e997625c07aa1213b19905b2.jpg"
    icon_path = "fish_coins_bot/img/icon.png"  # 本地图标路径

    # 获取背景图片
    background_image = await fetch_image(live_cover_url)

    # 调整背景图片尺寸到 640x360
    target_size = (640, 360)
    resized_background = background_image.resize(target_size, Image.Resampling.LANCZOS)

    # 创建一个白色半透明图层
    overlay = Image.new("RGBA", resized_background.size, (255, 255, 255, 128))  # 半透明白色滤镜
    background_with_overlay = Image.alpha_composite(resized_background.convert("RGBA"), overlay)

    # 获取头像图片
    avatar_image = await fetch_image(live_avatar_url)

    # 调整头像图片尺寸到 100x100
    avatar_size = (100, 100)
    resized_avatar = avatar_image.resize(avatar_size, Image.Resampling.LANCZOS)

    # 创建圆形头像蒙版
    mask = Image.new("L", avatar_size, 0)  # 创建黑色蒙版
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)  # 画一个白色圆

    # 将圆形蒙版应用到头像
    rounded_avatar = Image.new("RGBA", avatar_size, (255, 255, 255, 0))  # 创建透明背景
    rounded_avatar.paste(resized_avatar, (0, 0), mask)

    # 创建阴影
    shadow = Image.new("RGBA", (avatar_size[0] + 10, avatar_size[1] + 10), (0, 0, 0, 0))  # 增加阴影边距
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((5, 5, avatar_size[0] + 5, avatar_size[1] + 5), fill=(0, 0, 0, 150))  # 半透明黑色阴影
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))  # 高斯模糊使阴影更柔和

    # 加载字体
    font_path = "fish_coins_bot/fonts/ZCOOLKuaiLe-Regular.ttf"  # 替换为实际路径

    # 修改文字内容
    live_name = "喵不动了喵"  # 主文字
    live_address = "https://live.bilibili.com/3786110"  # 小文字
    additional_text = "扶贫！破产！啊啊啊！啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊"  # 需要添加的额外文字
    icon_text = "开播啦！"  # 文字后面加上的文字

    # 设置字体大小
    main_font_size = avatar_size[1] * 0.7  # 主文字大小与头像高度相关
    main_font = ImageFont.truetype(font_path, size=int(main_font_size))
    small_font_size = avatar_size[1] * 0.3  # 小文字高度约为主文字的 30%
    small_font = ImageFont.truetype(font_path, size=int(small_font_size))

    # 使用 getbbox 方法计算主文字的实际宽度和高度
    main_bbox = main_font.getbbox(live_name)
    main_text_width = main_bbox[2] - main_bbox[0]
    main_text_height = main_bbox[3] - main_bbox[1]

    # 使用 getbbox 方法计算小文字的实际宽度和高度
    small_bbox = small_font.getbbox(live_address)
    small_text_width = small_bbox[2] - small_bbox[0]
    small_text_height = small_bbox[3] - small_bbox[1]

    # 计算主文字和小文字的总高度
    total_text_height = main_text_height + small_text_height + 10  # 主文字和小文字之间间隔 10 像素

    # 设置整体布局的顶部固定位置
    layout_top = 20  # 距离顶部 20 像素

    # 设置头像的位置，使其垂直居中于文字总高度
    avatar_top = layout_top + (total_text_height - avatar_size[1]) // 2
    position = (
        target_size[0] - avatar_size[0] - 20,  # 距离右侧 20 像素
        avatar_top
    )

    # 绘制头像的阴影和头像本身
    background_with_overlay.paste(shadow, (position[0] - 5, position[1] - 5), shadow)  # 先粘贴阴影
    background_with_overlay.paste(rounded_avatar, position, rounded_avatar)  # 再粘贴圆形头像

    # 设置主文字的位置
    main_text_position = (
        position[0] - main_text_width - 20,  # 距离头像左侧 20 像素
        layout_top  # 主文字顶部对齐整体布局顶部
    )

    # 设置小文字的位置（右对齐主文字）
    small_text_position = (
        main_text_position[0] + main_text_width - small_text_width,  # 使小文字右对齐主文字
        main_text_position[1] + main_text_height + 10  # 主文字下方 10 像素
    )

    draw = ImageDraw.Draw(background_with_overlay)

    # 修改主文字颜色为白色，并添加光晕效果
    text_color = (255, 255, 255)  # 白色
    shadow_color = (255, 255, 255, 128)  # 半透明白色光晕

    # 绘制主文字光晕
    for offset in range(1, 6):  # 使用递增循环增强光晕效果
        glow_position = (main_text_position[0] - offset, main_text_position[1] - offset)
        draw.text(glow_position, live_name, font=main_font, fill=shadow_color)

    # 绘制主文字
    draw.text(main_text_position, live_name, font=main_font, fill=text_color)

    # 绘制小文字
    draw.text(small_text_position, live_address, font=small_font, fill=text_color)

    # 计算额外文字的位置，并对超长文本进行省略处理
    max_width = target_size[0] - 40  # 文字最大宽度
    extra_text_position = (main_text_position[0], small_text_position[1] + 30)

    # 处理额外文字，避免超出范围
    lines = []
    current_line = ""
    for word in additional_text.split(" "):
        if main_font.getbbox(current_line + " " + word)[2] - main_font.getbbox(current_line + " " + word)[0] <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())

    # 绘制额外文字
    for line in lines:
        draw.text(extra_text_position, line, font=small_font, fill=text_color)
        extra_text_position = (extra_text_position[0], extra_text_position[1] + small_text_height + 10)

    # 加载并缩放本地图标
    icon_image = Image.open(icon_path)  # 使用本地路径直接加载图像
    icon_size = (40, 40)  # 缩小图标的尺寸
    icon_resized = icon_image.resize(icon_size, Image.Resampling.LANCZOS)

    # 计算图标位置
    icon_position = (main_text_position[0], extra_text_position[1] + 20)

    # 将图标添加到图片
    background_with_overlay.paste(icon_resized, icon_position, icon_resized)

    # 绘制"开播啦！"文本
    icon_text_font = ImageFont.truetype(font_path, size=main_font_size * 0.5)
    icon_text_bbox = icon_text_font.getbbox(icon_text)
    icon_text_width = icon_text_bbox[2] - icon_text_bbox[0]
    icon_text_position = (icon_position[0] + icon_size[0] + 10, icon_position[1] + (icon_size[1] - icon_text_bbox[3]) // 2)

    # 绘制"开播啦！"文本
    draw.text(icon_text_position, icon_text, font=icon_text_font, fill=text_color)

    # 显示和保存最终图片
    background_with_overlay.show()  # 显示图片
    background_with_overlay.save("final_image_with_avatar_and_text_with_icon.png")  # 保存为 PNG 文件
    print("Final image saved as final_image_with_avatar_and_text_with_icon.png.")


if __name__ == "__main__":
    asyncio.run(test_fetch_image())
