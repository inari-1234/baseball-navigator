"""Synthetic screenshot bytes with an EXIF capture time (tests only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import struct
import zlib

JST = timezone(timedelta(hours=9))


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def exif_png(payload: bytes, captured: datetime) -> bytes:
    stamp = captured.strftime("%Y:%m:%d %H:%M:%S").encode() + b"\0"   # 20 bytes
    # Big-endian TIFF, IFD0 with one DateTime (0x0132) ASCII entry.
    tiff = b"MM\x00*" + struct.pack(">I", 8) + struct.pack(">H", 1)
    tiff += struct.pack(">HHII", 0x0132, 2, len(stamp), 8 + 2 + 12 + 4)
    tiff += struct.pack(">I", 0) + stamp
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"eXIf", tiff)
            + _chunk(b"tEXt", b"fixture\0" + payload)
            + _chunk(b"IDAT", zlib.compress(b"\0\0")) + _chunk(b"IEND", b""))


def fresh_capture(minutes_ago: int = 1) -> datetime:
    return (datetime.now(JST) - timedelta(minutes=minutes_ago)).replace(microsecond=0)
