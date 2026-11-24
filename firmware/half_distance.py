"""Measure detection range with the stationary ADC probe and a single reflector."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
from time import monotonic

from serial import Serial, SerialException


POSITIONS = ("1 左前", "2 右後ろ", "3 左後ろ", "4 右前")
OLD_TRIP = (1369, 655, 611, 1052)


def thresholds(index, record):
    # Use the upper part of the observed distribution for an instantaneous trip.
    if not math.isfinite(record["old_cm"]) or record["old_cm"] <= 0:
        raise ValueError("元の距離を確認してください。")
    values = record["half"]
    if len(values) != 32 or any(type(v) is not int or not 0 <= v <= 4095 for v in values):
        raise ValueError("測定データが不完全です。")
    ordered = sorted(values)
    target = ordered[27]
    floor = OLD_TRIP[index]
    if ordered[16] <= floor or target - floor < 16 or ordered[16] >= 4095:
        raise ValueError("この位置では元の距離との差を判別できません。紙を正対させて再測定してください。")
    trip = target
    release = max(floor, min(ordered[3], target - 16))
    return (index, True, trip, release)


def run(port_name, destination, first_cm=None):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("障害物の検知距離を半分に調整（モーター停止）")
    root.attributes("-topmost", True)
    box = ttk.Frame(root, padding=18)
    box.pack()
    title, hint, live, notice = (tk.StringVar() for _ in range(4))
    ttk.Label(box, textvariable=title, font=("Yu Gothic UI", 16)).pack(anchor="w")
    ttk.Label(box, textvariable=hint, wraplength=550).pack(anchor="w", pady=8)
    ttk.Label(box, textvariable=live).pack(anchor="w")
    distance = tk.StringVar()
    entry = ttk.Entry(box, textvariable=distance, width=10)
    entry.pack(anchor="w", pady=4)
    ttk.Label(box, textvariable=notice, foreground="#963511", wraplength=550).pack(anchor="w")
    records = []
    record = {"old_cm": first_cm} if first_cm else {}
    samples = deque(maxlen=32)
    phase = 1 if first_cm else 0
    last = 0
    port = None
    pending = bytearray()
    armed = False

    def display():
        i = len(records)
        title.set("センサー " + POSITIONS[i])
        if phase == 0:
            hint.set("白い紙を遠くからゆっくり近づけ、旧設定が初めて「検知」になる位置で止めます。センサー正面から紙までを測り、cmで入力して記録してください。")
            entry.configure(state="normal")
            distance.set("")
        else:
            d = record["old_cm"] * 0.5
            hint.set(f"同じ面と角度で、センサー正面から {d:.2f} cm に紙を置いてください。1秒間保持し、「この位置を記録」を押してください。")
            entry.configure(state="disabled")
        samples.clear()

    def save():
        nonlocal phase, record, armed
        if len(samples) < samples.maxlen or monotonic() - last > 0.4:
            notice.set("受信中です。紙を約1秒間固定してから記録してください。")
            return
        i = len(records)
        rows = list(samples)
        notice.set("")
        if phase == 0:
            try:
                d = float(distance.get())
                if not math.isfinite(d) or d <= 0:
                    raise ValueError()
            except ValueError:
                notice.set("測った距離をcmで入力してください。")
                return
            if max(rows) < OLD_TRIP[i] or not armed:
                notice.set("一度遠ざけて未検知にしてから、旧設定で反応する位置に合わせてください。")
                return
            record = {"old_cm": d, "original": rows}
        else:
            record["half"] = rows
            try:
                thresholds(i, record)
            except ValueError as error:
                notice.set(str(error))
                phase = 1
                display()
                return
            records.append(record)
            destination.with_suffix(".partial.json").write_text(json.dumps(records), encoding="utf-8")
            record = {}
            if len(records) == 4:
                destination.write_text(json.dumps(records, indent=2), encoding="utf-8")
                root.destroy()
                return
            armed = False
        phase = (phase + 1) % 2
        display()

    def poll():
        nonlocal port, last, armed
        try:
            if port is None:
                port = Serial(None, 9600, timeout=0)
                port.port = port_name
                port.dtr = port.rts = False
                port.open()
            pending.extend(port.read(port.in_waiting))
            while b"\n" in pending:
                line, _, tail = pending.partition(b"\n")
                pending[:] = tail
                if len(line) != 25 or line[0] != ord("@"):
                    continue
                i = len(records)
                try:
                    value = int(line[1 + 4*i:5 + 4*i], 16)
                except ValueError:
                    continue
                if value > 4095:
                    samples.clear()
                    continue
                last = monotonic()
                samples.append(value)
                if phase == 0 and value < OLD_TRIP[i]:
                    armed = True
                hit = "検知" if value >= OLD_TRIP[i] else "未検知"
                live.set(f"旧設定　{hit}　　　反応値　{value}")
            if len(pending) > 128:
                pending.clear()
        except (OSError, SerialException):
            if port is not None:
                port.close()
            port = None
            pending.clear()
        if monotonic() - last > 0.4:
            samples.clear()
            live.set("Load側で測定版の起動を待っています")
        root.after(50, poll)

    ttk.Button(box, text="この位置を記録", command=save).pack(anchor="w", pady=6)
    display()
    root.after(50, poll)
    try:
        root.mainloop()
    finally:
        if port is not None:
            port.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--port", default="COM12")
    parser.add_argument("--first-cm", type=float, help="Previously measured original range of sensor 1")
    args = parser.parse_args()
    run(args.port, args.destination, args.first_cm)
