"""P7-J: bind a "current" screenshot to its device capture time.

A reviewer's ``CURRENT_PRE_EXECUTION`` label alone cannot prove that an image is
fresh: an older screenshot with a new file name and hash would otherwise pass.
iPhone screenshots carry an EXIF capture time. The evidence-index record states
that time with its UTC offset (``captured_at``); this module reads the time from
the actual bytes, requires the two to agree, and requires the capture to fall
inside a short window before certification. Missing or unreadable capture time
fails closed. Standard library only; the image is never decoded or modified.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import struct

# Screenshots must be taken shortly before the certified reply.
MAX_CAPTURE_AGE = timedelta(minutes=30)
# Tolerate small device/server clock differences.
MAX_FUTURE_SKEW = timedelta(minutes=2)

_DATETIME = 0x0132
_EXIF_IFD = 0x8769
_DATETIME_ORIGINAL = 0x9003
_OFFSET_TIME_ORIGINAL = 0x9011
_OFFSET_TIME = 0x9010


class CaptureTimeError(ValueError):
    pass


def now_utc() -> datetime:
    """Certification clock. Tests patch this function."""
    return datetime.now(timezone.utc)


def _tiff_tags(tiff: bytes) -> dict[int, str]:
    if len(tiff) < 8 or tiff[:2] not in (b"MM", b"II"):
        raise CaptureTimeError("CAPTURE_TIME_UNREADABLE")
    endian = ">" if tiff[:2] == b"MM" else "<"

    def ifd(offset: int) -> dict[int, tuple[int, int, bytes]]:
        if offset + 2 > len(tiff):
            raise CaptureTimeError("CAPTURE_TIME_UNREADABLE")
        (count,) = struct.unpack_from(endian + "H", tiff, offset)
        entries = {}
        for i in range(count):
            pos = offset + 2 + i * 12
            if pos + 12 > len(tiff):
                raise CaptureTimeError("CAPTURE_TIME_UNREADABLE")
            tag, kind, n = struct.unpack_from(endian + "HHI", tiff, pos)
            entries[tag] = (kind, n, tiff[pos + 8:pos + 12])
        return entries

    def ascii_value(entry) -> str | None:
        kind, n, raw = entry
        if kind != 2:
            return None
        if n <= 4:
            data = raw[:n]
        else:
            (start,) = struct.unpack(endian + "I", raw)
            data = tiff[start:start + n]
        return data.split(b"\0", 1)[0].decode("ascii", "replace").strip() or None

    (first,) = struct.unpack_from(endian + "I", tiff, 4)
    root = ifd(first)
    values = {}
    if _DATETIME in root:
        values[_DATETIME] = ascii_value(root[_DATETIME])
    if _EXIF_IFD in root:
        (sub,) = struct.unpack(endian + "I", root[_EXIF_IFD][2])
        for tag, entry in ifd(sub).items():
            if tag in (_DATETIME_ORIGINAL, _OFFSET_TIME_ORIGINAL, _OFFSET_TIME):
                values[tag] = ascii_value(entry)
    return {k: v for k, v in values.items() if v}


def _exif_block(data: bytes) -> bytes:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        pos = 8
        while pos + 8 <= len(data):
            (length,) = struct.unpack_from(">I", data, pos)
            kind = data[pos + 4:pos + 8]
            if kind == b"eXIf":
                return data[pos + 8:pos + 8 + length]
            if kind == b"IEND":
                break
            pos += 12 + length
        raise CaptureTimeError("CAPTURE_TIME_REQUIRED")
    if data.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 4 <= len(data) and data[pos] == 0xFF:
            marker = data[pos + 1]
            (length,) = struct.unpack_from(">H", data, pos + 2)
            if marker == 0xE1 and data[pos + 4:pos + 10] == b"Exif\0\0":
                return data[pos + 10:pos + 2 + length]
            if marker == 0xDA:
                break
            pos += 2 + length
        raise CaptureTimeError("CAPTURE_TIME_REQUIRED")
    # HEIC and other containers are not parsed: fail closed.
    raise CaptureTimeError("CAPTURE_TIME_UNSUPPORTED_FORMAT")


def device_capture_time(data: bytes) -> tuple[datetime, str | None]:
    """Naive local capture time and its EXIF offset string when recorded."""
    tags = _tiff_tags(_exif_block(data))
    text = tags.get(_DATETIME_ORIGINAL) or tags.get(_DATETIME)
    if not text:
        raise CaptureTimeError("CAPTURE_TIME_REQUIRED")
    try:
        local = datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError as exc:
        raise CaptureTimeError("CAPTURE_TIME_UNREADABLE") from exc
    return local, tags.get(_OFFSET_TIME_ORIGINAL) or tags.get(_OFFSET_TIME)


def verify_fresh_capture(data: bytes, captured_at: object,
                         *, now: datetime | None = None) -> datetime:
    """Return the aware capture time or raise a stable error code."""
    if not isinstance(captured_at, str):
        raise CaptureTimeError("CAPTURE_TIME_REQUIRED")
    try:
        stated = datetime.fromisoformat(captured_at)
    except ValueError as exc:
        raise CaptureTimeError("CAPTURE_TIME_UNREADABLE") from exc
    if stated.tzinfo is None:
        raise CaptureTimeError("CAPTURE_TIME_OFFSET_REQUIRED")
    local, exif_offset = device_capture_time(data)
    if stated.replace(tzinfo=None, microsecond=0) != local:
        raise CaptureTimeError("CAPTURE_TIME_MISMATCH")
    if exif_offset is not None:
        sign = 1 if exif_offset.startswith("+") else -1
        try:
            hours, minutes = (int(v) for v in exif_offset[1:].split(":"))
        except ValueError as exc:
            raise CaptureTimeError("CAPTURE_TIME_UNREADABLE") from exc
        if stated.utcoffset() != sign * timedelta(hours=hours, minutes=minutes):
            raise CaptureTimeError("CAPTURE_TIME_MISMATCH")
    current = now or now_utc()
    if stated > current + MAX_FUTURE_SKEW or current - stated > MAX_CAPTURE_AGE:
        raise CaptureTimeError("CURRENT_CAPTURE_NOT_FRESH")
    return stated
