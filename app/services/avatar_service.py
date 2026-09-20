import logging
from pathlib import Path
from time import time_ns

from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.models import User


_SIGNATURES = {
    "jpg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),
}

logger = logging.getLogger(__name__)


async def save_avatar(upload: UploadFile, user: User, settings: Settings) -> str:
    data = await upload.read(settings.app_avatar_max_bytes + 1)
    if not data or len(data) > settings.app_avatar_max_bytes:
        raise HTTPException(status_code=413, detail="头像文件为空或超过大小限制")
    extension = _detect_extension(data)
    avatar_dir = Path(settings.app_media_root).resolve() / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    for old_extension in _SIGNATURES:
        old_path = avatar_dir / f"{user.id}.{old_extension}"
        if old_path.exists() and old_extension != extension:
            old_path.unlink()
    target = avatar_dir / f"{user.id}.{extension}"
    target.write_bytes(data)
    # The version query avoids showing a browser-cached previous avatar after replacement.
    return f"/media/avatars/{target.name}?v={time_ns()}"


def _detect_extension(data: bytes) -> str:
    if data.startswith(_SIGNATURES["jpg"][0]):
        return "jpg"
    if data.startswith(_SIGNATURES["png"][0]):
        return "png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    raise HTTPException(status_code=415, detail="头像仅支持 JPEG、PNG 或 WebP")


def remove_avatar_files(user_id: object, settings: Settings) -> None:
    avatar_dir = Path(settings.app_media_root).resolve() / "avatars"
    for extension in _SIGNATURES:
        path = avatar_dir / f"{user_id}.{extension}"
        if path.exists():
            try:
                path.unlink()
            except OSError:
                # The database account has already been deleted. Leave cleanup
                # for maintenance instead of returning an ambiguous API error.
                logger.warning("avatar-cleanup-failed user_id=%s path=%s", user_id, path)
