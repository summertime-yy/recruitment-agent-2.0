import logging

from minio import Minio

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_minio_client: Minio | None = None


def get_minio() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE,
        )
    return _minio_client


def ensure_buckets(bucket_names: list[str]) -> None:
    try:
        client = get_minio()
        for bucket in bucket_names:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                logger.info(f"Created MinIO bucket: {bucket}")
    except Exception as e:
        logger.warning(f"MinIO not available, skipping bucket creation: {e}")
