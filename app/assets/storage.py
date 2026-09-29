"""S3-compatible object storage (MinIO in dev) through one aioboto3 session."""

import aioboto3
from botocore.exceptions import ClientError

from app.config import settings

_session = aioboto3.Session()


def _client():
    return _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )


def public_url(key: str) -> str:
    return f"{settings.s3_public_base_url.rstrip('/')}/{key}"


async def put(key: str, data: bytes, content_type: str) -> None:
    # ponytail: whole-body put_object; fine at the 10 MB cap, switch to multipart if it grows.
    async with _client() as s3:
        await s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


async def delete(key: str) -> None:
    async with _client() as s3:
        await s3.delete_object(Bucket=settings.s3_bucket, Key=key)


async def exists(key: str) -> bool:
    async with _client() as s3:
        try:
            await s3.head_object(Bucket=settings.s3_bucket, Key=key)
        except ClientError:
            return False
        return True
