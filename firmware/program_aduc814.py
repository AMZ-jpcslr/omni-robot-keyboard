"""Program an ADuC814 via its version 2 serial loader (AN-1074)."""

import argparse
from pathlib import Path

from serial import Serial


def load_image(path):
    """Read SDCC's 16-bit Intel HEX and validate the entire image before erasure."""
    image = {}
    eof = False
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not line.strip():
            continue
        if eof or not line.startswith(":"):
            raise ValueError(f"HEX record {number}: unexpected data")
        data = bytes.fromhex(line[1:])
        if len(data) < 5 or data[0] + 5 != len(data) or sum(data) & 255:
            raise ValueError(f"HEX record {number}: length or checksum")
        start = int.from_bytes(data[1:3], "big")
        kind = data[3]
        if kind == 1 and data[:3] == bytes(3):
            eof = True
            continue
        if kind != 0 or start + data[0] > 8192:
            raise ValueError(f"HEX record {number}: unsupported address or type")
        for address, value in enumerate(data[4:-1], start):
            if address in image:
                raise ValueError(f"HEX record {number}: overlapping address")
            image[address] = value
    if not eof or not all(k in image for k in (0, 1, 2)) or image[0] != 0x02:
        raise ValueError("SDCC reset vector or EOF missing")
    target = image[1] * 256 + image[2]
    if target not in image:
        raise ValueError("SDCC reset vector points outside image")
    return bytes(image.get(i, 255) for i in range(max(image) + 1))


def command(port, payload):
    body = bytes([len(payload)]) + payload
    frame = b"\x07\x0e" + body + bytes([-sum(body) & 255])
    if port.write(frame) != len(frame):
        raise OSError("Incomplete serial write")
    reply = port.read(1)
    if reply != b"\x06":
        raise OSError(f"Command {payload[:4].hex(' ')}: {reply.hex() or 'no response'}")


def identify(port):
    port.reset_input_buffer()
    if port.write(bytes.fromhex("21 5a 00 a6")) != 4:
        raise OSError("Incomplete identification request")
    reply = port.read(25)
    if len(reply) != 25 or not reply.startswith(b"ADI 814   V2") or sum(reply) & 255:
        raise OSError("ADuC814 loader ID missing or checksum invalid")
    return reply


def program(port, image):
    identify(port)
    command(port, b"C")  # Code space only. Leave nonvolatile data memory intact.
    for address in range(0, len(image), 16):
        command(port, b"W" + address.to_bytes(3, "big") + image[address:address + 16])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--write", type=Path, metavar="MAPPED_FIRMWARE.ihx",
                        help="Erase program memory and write this SDCC image")
    args = parser.parse_args()
    image = load_image(args.write) if args.write else None
    with Serial(None, 9600, timeout=2, write_timeout=1) as port:
        port.dtr = port.rts = False
        port.port = args.port
        port.open()
        if image is None:
            print(repr(identify(port)[:14]))
        else:
            program(port, image)
            print(f"Loader acknowledged all writes ({len(image)} bytes).")


if __name__ == "__main__":
    main()
