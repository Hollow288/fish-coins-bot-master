from pathlib import Path
import yt_dlp
from nonebot.log import logger

from fish_coins_bot.utils.minio_client import minio_client
from minio.error import S3Error

SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mov', '.avi'}


def download_video_code(url: str):
    download_video_dir = (
            Path(__file__).parent.parent.parent / "downloads" / "video"
    )
    download_video_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'outtmpl': str(download_video_dir / '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'retries': 10,
        'fragment_retries': 10,
        'ignoreerrors': True,
    }

    try:
        logger.info(f"正在准备解析: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        logger.success(f">>> 下载阶段完成: {url}")
    except Exception as e:
        logger.error(f"下载出错: {e}")
        raise e  # 抛出异常以便外层捕获


def object_exists(bucket, object_name) -> bool:
    try:
        minio_client.stat_object(bucket, object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise


def sync_local_videos_to_minio():

    video_dir = Path(__file__).parent.parent.parent / "downloads" / "video"
    bucket_name = "big-file"

    if not video_dir.exists():
        logger.warning("下载目录不存在，跳过同步")
        return

    for video_file in video_dir.iterdir():
        if video_file.is_dir():
            continue

        if video_file.suffix == '.uploaded':
            continue

        if video_file.suffix not in SUPPORTED_EXTENSIONS:
            logger.debug(f"跳过非视频文件: {video_file.name}")
            continue

        object_name = f"movies/{video_file.name}"

        if object_exists(bucket_name, object_name):
            logger.info(f"MinIO已存在，标记为已上传: {video_file.name}")
            new_path = video_file.with_name(f"{video_file.name}.uploaded")
            video_file.rename(new_path)
            continue

        logger.warning(f"开始上传文件: {video_file.name}")

        try:
            minio_client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=str(video_file),
                content_type="video/mp4"
            )

            logger.success(f"上传完成: {video_file.name}")

            new_path = video_file.with_name(f"{video_file.name}.uploaded")
            video_file.rename(new_path)


        except Exception as e:
            logger.error(f"上传失败 {video_file.name}: {e}")


def task_workflow(url: str):
    # 1. 执行下载
    download_video_code(url)

    sync_local_videos_to_minio()
