"""Optional Rachio zone photo import helpers."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

MAX_IMAGE_BYTES = 8 * 1024 * 1024
PHOTO_TIMEOUT_SECONDS = 20
PHOTO_MAX_WIDTH = 960
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


@dataclass(frozen=True, slots=True)
class ZonePhotoImportResult:
    """Result of a single optional zone photo import attempt."""

    status: str
    image_url: str | None = None
    reason: str | None = None

    @property
    def rachio_image_available(self) -> bool:
        """Return whether Rachio exposed an image URL for this zone."""
        return bool(self.image_url) or self.status == "cached"


def imported_zone_photo_paths(config_path, zone_id: str) -> tuple[Path, str]:
    """Return the HA filesystem and public URL for one imported zone image."""
    safe_zone_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in zone_id
    ).strip("-_")
    safe_zone_id = safe_zone_id or "zone"
    path = Path(
        config_path(
            "www",
            "rachio-supervisor",
            "imported-zones",
            f"{safe_zone_id}.jpg",
        )
    )
    return path, f"/local/rachio-supervisor/imported-zones/{safe_zone_id}.jpg"


def import_rachio_zone_photo(
    *,
    client,
    zone_id: str | None,
    config_path,
    import_enabled: bool,
) -> ZonePhotoImportResult:
    """Import and cache a Rachio zone photo when enabled and available."""
    if not import_enabled:
        return ZonePhotoImportResult(status="disabled")
    if not zone_id:
        return ZonePhotoImportResult(status="missing", reason="zone_unresolved")

    cache_path, _cache_url = imported_zone_photo_paths(config_path, zone_id)
    if cache_path.exists():
        return ZonePhotoImportResult(status="cached")

    try:
        zone = client.get_zone(zone_id)
    except Exception as err:  # noqa: BLE001 - non-fatal optional import path
        return ZonePhotoImportResult(status="failed", reason=str(err)[:220])

    image_url = zone.get("imageUrl") if isinstance(zone, dict) else None
    if not isinstance(image_url, str) or not image_url:
        return ZonePhotoImportResult(status="missing", reason="imageUrl_missing")

    try:
        payload, content_type = _download_image(image_url)
        image_bytes = _resize_to_dashboard_jpeg(payload, content_type)
        _atomic_write(cache_path, image_bytes)
    except ValueError as err:
        return ZonePhotoImportResult(
            status="rejected",
            image_url=image_url,
            reason=str(err)[:220],
        )
    except Exception as err:  # noqa: BLE001 - non-fatal optional import path
        return ZonePhotoImportResult(
            status="failed",
            image_url=image_url,
            reason=str(err)[:220],
        )
    return ZonePhotoImportResult(status="imported", image_url=image_url)


def _download_image(image_url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        image_url,
        headers={"User-Agent": "RachioSupervisor/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=PHOTO_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise ValueError(f"unsupported_content_type:{content_type or 'missing'}")
            content_length = _content_length(response.headers.get("content-length"))
            if content_length is not None and content_length > MAX_IMAGE_BYTES:
                raise ValueError("image_too_large")
            payload = response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.URLError as err:
        raise ValueError(f"download_failed:{err}") from err
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")
    if not payload:
        raise ValueError("empty_image")
    return payload, content_type


def _content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _resize_to_dashboard_jpeg(payload: bytes, content_type: str) -> bytes:
    try:
        from PIL import Image
    except ModuleNotFoundError:
        if content_type in {"image/jpeg", "image/jpg"}:
            return payload
        raise ValueError("pillow_unavailable_for_non_jpeg") from None

    with Image.open(BytesIO(payload)) as image:
        image = image.convert("RGB")
        if image.width > PHOTO_MAX_WIDTH:
            ratio = PHOTO_MAX_WIDTH / image.width
            height = max(1, int(image.height * ratio))
            image = image.resize((PHOTO_MAX_WIDTH, height))
        output = BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True)
        return output.getvalue()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(payload)
    temp_path.replace(path)
