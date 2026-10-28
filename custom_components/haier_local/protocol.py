"""Local TCP client for Haier uSDK Wi-Fi modules (plaintext port 56800).

Envelope (80 bytes) + smartair2 frame. Layout and the 6d01/4d5f word layout follow
the reverse-engineering in bwitosze/haier-smartair2-cloud-for-homeassistant (MIT).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

DEFAULT_PORT = 56800
MARKER_TX = 0x2714
MARKER_RX = 0x2715
TIMEOUT = 6
QUIET = 0.8  # silence after the last frame that ends one poll exchange

MODE_AUTO, MODE_COOL, MODE_HEAT, MODE_FAN, MODE_DRY = 0, 1, 2, 3, 4
FAN_HIGH, FAN_MID, FAN_LOW, FAN_AUTO = 0, 1, 2, 3

_SWING_V_BIT = 1 << 0
_QUIET_BIT = 1 << 2
_TURBO_BIT = 1 << 1


class HaierError(Exception):
    """Communication or protocol failure."""


@dataclass
class HaierState:
    power: bool
    mode: int
    fan: int
    swing_v: bool
    quiet: bool
    turbo: bool
    target_temp: int
    current_temp: int
    raw: bytes  # 24-byte status block (12 big-endian words)


def normalise_mac(mac: str) -> str:
    cleaned = "".join(c for c in mac if c.isalnum()).upper()
    if len(cleaned) != 12:
        raise ValueError(f"MAC must have 12 hex chars: {mac!r}")
    return cleaned


def build_frame(ftype: int, subcmd: bytes, data: bytes = b"") -> bytes:
    body = bytes([8 + len(subcmd) + len(data), 0, 0, 0, 0, 0, 0, ftype]) + subcmd + data
    return b"\xff\xff" + body + bytes([sum(body) & 0xFF])


def _envelope(payload: bytes, mac: str, seq: int) -> bytes:
    env = bytearray(80)
    env[2:4] = MARKER_TX.to_bytes(2, "big")
    env[40:52] = mac.encode("ascii")
    env[75] = seq & 0xFF
    env[79] = len(payload)
    return bytes(env) + payload


def decode_status(frame: bytes) -> HaierState:
    data = frame[12 : 2 + frame[2]]
    w = [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data) - 1, 2)]
    if len(w) < 12:
        raise HaierError("short status frame")
    return HaierState(
        power=bool(w[8] & 1),
        mode=w[5],
        fan=w[6],
        swing_v=bool(w[7] & _SWING_V_BIT),
        quiet=bool(w[9] & _QUIET_BIT),
        turbo=bool(w[9] & _TURBO_BIT),
        target_temp=w[11] + 16,
        current_temp=w[0],
        raw=bytes(data[:24]),
    )


def encode_set(state: HaierState, **changes) -> bytes:
    """Read-modify-write: full 24-byte 4d5f block from the last status plus changes."""
    mode = changes.get("mode", state.mode)
    fan = changes.get("fan", state.fan)
    target = changes.get("target_temp", state.target_temp)
    power = changes.get("power", state.power)
    w7 = int.from_bytes(state.raw[14:16], "big")
    w9 = int.from_bytes(state.raw[18:20], "big")
    w10 = int.from_bytes(state.raw[20:22], "big")
    for key, bit in (("swing_v", _SWING_V_BIT),):
        if key in changes:
            w7 = (w7 | bit) if changes[key] else (w7 & ~bit)
    for key, bit in (("quiet", _QUIET_BIT), ("turbo", _TURBO_BIT)):
        if key in changes:
            w9 = (w9 | bit) if changes[key] else (w9 & ~bit)
    blk = bytearray(24)
    blk[10:12] = int(mode).to_bytes(2, "big")
    blk[12:14] = int(fan).to_bytes(2, "big")
    blk[14:16] = (w7 & 0xFFFF).to_bytes(2, "big")
    blk[16:18] = (1 if power else 0).to_bytes(2, "big")
    blk[18:20] = (w9 & 0xFFFF).to_bytes(2, "big")
    blk[20:22] = (w10 & 0xFFFF).to_bytes(2, "big")
    blk[22:24] = (int(target) - 16).to_bytes(2, "big")
    return build_frame(0x01, b"\x4d\x5f", bytes(blk))


class HaierClient:
    """Short-lived connection per operation (the module serves one client at a time)."""

    def __init__(self, host: str, mac: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.mac = normalise_mac(mac)
        self.port = port
        self._lock = asyncio.Lock()

    async def _read_frames(self, reader: asyncio.StreamReader, until_status: bool) -> bytes | None:
        """Return the last 6d01 status payload before the link goes quiet (None if none came)."""
        last = None
        try:
            while True:
                wait = QUIET if last else TIMEOUT
                header = await asyncio.wait_for(reader.readexactly(80), wait)
                plen = header[79]
                payload = await asyncio.wait_for(reader.readexactly(plen), TIMEOUT) if plen else b""
                if int.from_bytes(header[2:4], "big") != MARKER_RX:
                    continue
                if len(payload) >= 12 and payload[9] in (0x02, 0x06) and payload[10:12] == b"\x6d\x01":
                    last = payload
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return last

    async def _session(self, change: dict | None) -> HaierState:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), TIMEOUT
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise HaierError(f"cannot connect to {self.host}: {err}") from err
        try:
            seq = 0

            async def poll() -> HaierState:
                nonlocal seq
                seq += 1
                writer.write(_envelope(build_frame(0x01, b"\x4d\x01"), self.mac, seq))
                await writer.drain()
                # the module also pushes unsolicited frames; the reply to the poll is the last
                payload = await self._read_frames(reader, True)
                if payload is None:
                    raise HaierError("no status reply")
                return decode_status(payload)

            state = await poll()
            if change:
                seq += 1
                writer.write(_envelope(encode_set(state, **change), self.mac, seq))
                await writer.drain()
                await asyncio.sleep(1.0)
                state = await poll()
            return state
        except OSError as err:
            raise HaierError(str(err)) from err
        finally:
            writer.close()

    async def read_state(self) -> HaierState:
        async with self._lock:
            return await self._session(None)

    async def set_state(self, **change) -> HaierState:
        async with self._lock:
            return await self._session(change)
