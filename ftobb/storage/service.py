import time
from io import BytesIO
from typing import BinaryIO, Self

from minio import Minio


class StorageService:
    def __init__(
        self: Self,
        minio: Minio,
        bucket: str,
        get_url_expiry_seconds: int = 3600,
    ) -> None:
        self._minio = minio
        self._bucket = bucket
        self._get_url_expiry_seconds = get_url_expiry_seconds

    async def upload(
        self: Self, user_id: int, obj_name: str, content: bytes | BinaryIO
    ) -> str:
        """Upload an object to s3 and return object key."""
        obj_key = f"users/{user_id}/{time.time()}_{obj_name}"

        if isinstance(content, bytes):
            content = BytesIO(content)

        content.seek(0, 2)  # Seek to end
        file_size = content.tell()
        content.seek(0)

        self._minio.put_object(
            bucket_name=self._bucket,
            object_name=obj_key,
            data=content,
            length=file_size,
        )

        return obj_key

    async def get_signed_get_url(self: Self, obj_key: str) -> str:
        """Get a presigned GET url for given object that expires in 1 hour."""
        return self._minio.presigned_get_object(self._bucket, obj_key)
