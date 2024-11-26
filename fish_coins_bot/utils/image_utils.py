from PIL import Image
import httpx
from io import BytesIO
from nonebot.log import logger

async def fetch_image(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            return image
        else:
            logger.error(f"Failed to fetch image. Status code: {response.status_code}")
