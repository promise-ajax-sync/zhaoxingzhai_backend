import io
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.models import User
from app.services.avatar_service import remove_avatar_files, save_avatar


def _user() -> User:
    return User(id=uuid.uuid4(), email="avatar@example.com", is_anonymous=False)


@pytest.fixture
def media_root() -> Path:
    path = Path.cwd() / ".test-media" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize(
    ("filename", "content", "extension"),
    [
        ("avatar.jpg", b"\xff\xd8\xff" + b"jpeg-data", "jpg"),
        ("avatar.png", b"\x89PNG\r\n\x1a\n" + b"png-data", "png"),
        ("avatar.webp", b"RIFF\x00\x00\x00\x00WEBP" + b"webp-data", "webp"),
    ],
)
async def test_save_avatar_detects_content_and_writes_file(
    media_root: Path, filename: str, content: bytes, extension: str
) -> None:
    user = _user()
    settings = Settings(app_media_root=str(media_root))
    upload = UploadFile(filename=filename, file=io.BytesIO(content))

    url = await save_avatar(upload, user, settings)

    assert url.startswith(f"/media/avatars/{user.id}.{extension}?v=")
    assert (media_root / "avatars" / f"{user.id}.{extension}").read_bytes() == content


async def test_save_avatar_rejects_unknown_content(media_root: Path) -> None:
    upload = UploadFile(filename="avatar.png", file=io.BytesIO(b"not-an-image"))

    with pytest.raises(HTTPException) as error:
        await save_avatar(upload, _user(), Settings(app_media_root=str(media_root)))

    assert error.value.status_code == 415


async def test_save_avatar_rejects_oversized_content(media_root: Path) -> None:
    settings = Settings(app_media_root=str(media_root), app_avatar_max_bytes=65536)
    upload = UploadFile(
        filename="avatar.jpg",
        file=io.BytesIO(b"\xff\xd8\xff" + b"x" * 65536),
    )

    with pytest.raises(HTTPException) as error:
        await save_avatar(upload, _user(), settings)

    assert error.value.status_code == 413


def test_remove_avatar_files_removes_all_supported_variants(media_root: Path) -> None:
    user = _user()
    avatar_dir = media_root / "avatars"
    avatar_dir.mkdir()
    for extension in ("jpg", "png", "webp"):
        (avatar_dir / f"{user.id}.{extension}").write_bytes(b"avatar")

    remove_avatar_files(user.id, Settings(app_media_root=str(media_root)))

    assert list(avatar_dir.iterdir()) == []
