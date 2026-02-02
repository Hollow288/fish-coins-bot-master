import os

from minio import Minio
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("ENDPOINT")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


MINIO_CONFIG = {
    "endpoint": ENDPOINT,
    "access_key": ACCESS_KEY,
    "secret_key": SECRET_KEY,
    "secure": False
}

minio_client = Minio(
    endpoint=MINIO_CONFIG["endpoint"],
    access_key=MINIO_CONFIG["access_key"],
    secret_key=MINIO_CONFIG["secret_key"],
    secure=MINIO_CONFIG["secure"],
)
