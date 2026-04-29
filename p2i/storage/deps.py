from minio import Minio

from p2i.config import settings
from p2i.storage.service import StorageService

__storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global __storage_service  # noqa: PLW0603

    if not __storage_service:
        minio = Minio(
            settings.s3.endpoint,
            settings.s3.access_key,
            settings.s3.secret_key,
            secure=settings.s3.secure,
        )

        __storage_service = StorageService(
            minio, settings.s3.bucket, settings.s3.get_url_expiry_seconds
        )

    return __storage_service
