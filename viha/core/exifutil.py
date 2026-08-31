from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


def read_jpeg_exif(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        return {"error": "Not a JPEG"}
    i = 2
    exif = b""
    while i < len(data) - 4:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker == 0xDA:
            break
        seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker == 0xE1 and data[i + 4 : i + 10] == b"Exif\x00\x00":
            exif = data[i + 10 : i + 2 + seglen]
            break
        i += 2 + seglen
    if not exif:
        return {"note": "No EXIF block"}
    return _parse_tiff(exif)


def _parse_tiff(buf: bytes) -> dict[str, Any]:
    endian = "<" if buf[:2] == b"II" else ">"
    out: dict[str, Any] = {}
    try:
        offset = struct.unpack(endian + "I", buf[4:8])[0]
        out.update(_ifd(buf, offset, endian))
    except (struct.error, IndexError):
        return {"note": "EXIF present but unreadable"}
    return out


def _ifd(buf: bytes, offset: int, endian: str) -> dict[str, Any]:
    tags = {
        0x010F: "camera_make",
        0x0110: "camera_model",
        0x0132: "datetime",
        0x011A: "x_resolution",
        0x0100: "image_width",
        0x0101: "image_height",
        0x8825: "gps_ifd",
    }
    n = struct.unpack(endian + "H", buf[offset : offset + 2])[0]
    found: dict[str, Any] = {}
    gps_off = None
    for i in range(n):
        e = offset + 2 + i * 12
        tag, typ, count = struct.unpack(endian + "HHI", buf[e : e + 8])
        val = buf[e + 8 : e + 12]
        name = tags.get(tag)
        if not name:
            continue
        if name == "gps_ifd":
            gps_off = struct.unpack(endian + "I", val)[0]
            continue
        if typ == 2:
            voff = struct.unpack(endian + "I", val)[0] if count > 4 else None
            raw = buf[voff : voff + count] if voff else val[:count]
            found[name] = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        elif typ == 3 and count == 1:
            found[name] = struct.unpack(endian + "H", val[:2])[0]
        elif typ == 4 and count == 1:
            found[name] = struct.unpack(endian + "I", val)[0]
    if gps_off:
        found.update(_gps(buf, gps_off, endian))
    return found


def _gps(buf: bytes, offset: int, endian: str) -> dict[str, Any]:
    try:
        n = struct.unpack(endian + "H", buf[offset : offset + 2])[0]
    except struct.error:
        return {}
    vals: dict[int, Any] = {}
    for i in range(n):
        e = offset + 2 + i * 12
        tag, typ, count = struct.unpack(endian + "HHI", buf[e : e + 8])
        val = buf[e + 8 : e + 12]
        if typ == 2:
            voff = struct.unpack(endian + "I", val)[0] if count > 4 else None
            raw = buf[voff : voff + count] if voff else val[:count]
            vals[tag] = raw.split(b"\x00", 1)[0].decode("ascii", "replace")
        elif typ == 5:
            voff = struct.unpack(endian + "I", val)[0]
            rats = []
            for k in range(min(count, 3)):
                a, b = struct.unpack(endian + "II", buf[voff + k * 8 : voff + k * 8 + 8])
                rats.append(a / b if b else 0)
            vals[tag] = rats
    lat = _coord(vals.get(2), vals.get(1))
    lon = _coord(vals.get(4), vals.get(3))
    out: dict[str, Any] = {}
    if lat is not None and lon is not None:
        out["gps"] = f"{lat:.6f},{lon:.6f}"
        out["maps"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
    return out


def _coord(rationals: Any, ref: Any) -> float | None:
    if not rationals or len(rationals) < 3:
        return None
    deg, minutes, seconds = rationals[:3]
    dec = deg + minutes / 60 + seconds / 3600
    if ref in {"S", "W"}:
        dec = -dec
    return dec
