"""Capture stationary probe readings and derive four uniquely identified inputs."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import monotonic

from serial import Serial


def capture(device):
    rows = []
    with Serial(None, 9600, timeout=0.15) as port:
        port.port = device
        port.dtr = port.rts = False
        port.open()
        port.reset_input_buffer()
        deadline = monotonic() + 4
        while monotonic() < deadline and len(rows) < 64:
            line = port.readline().strip()
            if len(line) == 25 and line.startswith(b"@"):
                try:
                    row = [int(line[i:i + 4], 16) for i in range(1, 25, 4)]
                except ValueError:
                    continue
                if max(row) <= 4095:
                    rows.append(row)
    if len(rows) != 64:
        raise ValueError(f"有効な6入力の受信は {len(rows)}/64 行です")
    return rows


def fit(groups):
    settings = []
    for index in range(1, 5):
        candidates = []
        for ch in range(6):
            near = [row[ch] for row in groups[str(index)]]
            clear = [row[ch] for name, rows in groups.items() if name != str(index)
                     for row in rows]
            rising = median(near) > median(clear)
            sign = 1 if rising else -1
            clear_limit = max(sign * v for v in clear)
            near_limit = min(sign * v for v in near)
            gap = near_limit - clear_limit
            if gap >= 64:
                candidates.append((ch, rising, sign * (clear_limit + gap // 2),
                                   sign * (clear_limit + gap // 3)))
        if len(candidates) != 1:
            raise ValueError(f"センサー{index}の独立した入力候補 {candidates}。再測定してください")
        settings.append(candidates[0])
    if len({s[0] for s in settings}) != 4:
        raise ValueError("複数のセンサーが同じ入力を使用しています")
    return settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("step", choices=["clear", "1", "2", "3", "4", "clear_end", "fit"])
    parser.add_argument("--port", default="COM12")
    args = parser.parse_args()
    args.folder.mkdir(exist_ok=True, parents=True)
    if args.step != "fit":
        samples = capture(args.port)
        (args.folder / (args.step + ".json")).write_text(json.dumps(samples), encoding="ascii")
        print([(min(c), median(c), max(c)) for c in zip(*samples)])
    else:
        groups = {k: json.loads((args.folder / (k + ".json")).read_text())
                  for k in ("clear", "1", "2", "3", "4", "clear_end")}
        print(fit(groups))
