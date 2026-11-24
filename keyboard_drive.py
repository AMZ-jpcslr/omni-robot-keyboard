"""全方向ロボットを矢印キーで操作する。標準起動は画面内の車体を動かす。"""

import argparse
import json
from pathlib import Path
import tkinter as tk
from time import monotonic

from serial import Serial, SerialException
from serial.tools.list_ports import comports

from drive_preview import DrivePreview


KEYS = {"Up": "forward", "Down": "backward", "Left": "left", "Right": "right"}
WASD = {"w": "forward", "s": "backward", "a": "left", "d": "right"}
LABELS = {"forward": "↑ 前進", "backward": "↓ 後退", "left": "← 左移動",
          "right": "→ 右移動", "stop": "停止", "front_left": "↖ 左前",
          "front_right": "↗ 右前", "rear_left": "↙ 左後ろ", "rear_right": "↘ 右後ろ",
          "turn_left": "左旋回", "turn_right": "右旋回"}
MOVES = {"forward": ("forward",), "backward": ("backward",),
         "left": ("left",), "right": ("right",),
         "front_left": ("forward", "left"), "front_right": ("forward", "right"),
         "rear_left": ("backward", "left"), "rear_right": ("backward", "right")}
TURNS = ("turn_left", "turn_right")
CHORDS = {frozenset(actions): move for move, actions in MOVES.items()}
CHORDS.update({frozenset((turn,)): turn for turn in TURNS})
MIXED = []
for turn in TURNS:
    for move, actions in MOVES.items():
        name = f"{move}+{turn}"
        MIXED.append(name)
        CHORDS[frozenset((*actions, turn))] = name
        LABELS[name] = f"{LABELS[move]} ＋ {LABELS[turn]}"
ADUC_FRAMES = {name: bytes((0xA5, code, 0xFF ^ code))
               for code, name in enumerate(("stop", *MOVES, *TURNS))}
V3_FRAMES = {**ADUC_FRAMES, **{name: bytes((0xA5, code, 0xFF ^ code))
                              for code, name in enumerate(MIXED, 11)}}

# With wheel 1 forward, the floor test after the quarter-turn adjustment
# showed both axes were reversed. Map physical directions to wire frames.
FRONT1_FRAMES = {
    "forward": ADUC_FRAMES["right"],
    "backward": ADUC_FRAMES["left"],
    "left": ADUC_FRAMES["forward"],
    "right": ADUC_FRAMES["backward"],
    "stop": ADUC_FRAMES["stop"],
}


def await_receiver(port):
    """Listen only until the new firmware identifies itself."""
    port.reset_input_buffer()
    deadline = monotonic() + 2
    line = bytearray()
    while monotonic() < deadline:
        byte = port.read(1)
        if byte == b"\n":
            if line in (b"OMNI814/1", b"OMNI814/2", b"OMNI814/3", b"OMNI814/4"):
                return int(line[-1:])
            line.clear()
        elif byte:
            line.extend(byte)
            if len(line) > 32:
                line[:] = b"?"
    raise ValueError("新しい受信プログラムの識別応答がありません。USB送信は0件です")


def read_profile(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    baud = data["baudrate"]
    if type(baud) is not int or baud <= 0:
        raise ValueError("baudrate には通信速度を指定してください")
    frames = {key: bytes.fromhex(data["frames"][key]) for key in FRONT1_FRAMES}
    if not all(frames.values()) or len(set(frames.values())) != len(frames):
        raise ValueError("4方向と停止に別々の空でないフレームが必要です")
    return baud, frames


class Controller:
    def __init__(self, send, frames=V3_FRAMES, turn_keys=("q", "e")):
        self.send = send
        self.frames = frames
        self.bindings = {**KEYS, **WASD}
        if "turn_left" in frames:
            self.bindings.update(zip(turn_keys, TURNS))
        self.keys = set()
        self.blocked = False
        self.direction = "stop"

    def change(self, key, down):
        if len(key) == 1:
            key = key.lower()
        if key not in self.bindings and key != "space":
            return
        if down:
            self.keys.add(key)
        else:
            self.keys.discard(key)
        # Track physical keys separately so releasing W while ↑ is held keeps moving.
        actions = frozenset(self.bindings.get(k, "stop") for k in self.keys)
        direction = CHORDS.get(actions, "stop")
        if not actions:
            self.blocked = False
        elif direction == "stop" or direction not in self.frames:
            self.blocked = True
        self.set_direction("stop" if self.blocked else direction)

    def set_direction(self, direction):
        if direction != self.direction:
            self.send(direction)
            self.direction = direction

    def suspend(self):
        self.set_direction("stop")
        self.keys.clear()
        self.blocked = True


def run_window(port=None, frames=None, repeat=False, turn_keys=("q", "e"), guarded=False):
    import ctypes

    root = tk.Tk()
    root.title("全方向ロボット")
    root.resizable(False, False)
    status = tk.StringVar(value="停止")
    sensor_status = tk.StringVar(value="センサー受信待ち")
    mode = f"実機操作　{port.port}" if port else "全方向走行シミュレーター（USB送信なし）"
    tk.Label(root, text=mode).pack(padx=36, pady=(18, 0))
    preview = None if port else DrivePreview(root)
    tk.Label(root, textvariable=status, font=("Yu Gothic UI", 26),
             width=20).pack(pady=12)
    if guarded:
        tk.Label(root, textvariable=sensor_status).pack(pady=(0, 8))
    if preview is not None:
        frames = V3_FRAMES
    extended = "turn_left" in frames
    hints = "矢印・WASD で移動　／　離すと停止"
    if extended:
        hints += (f"　／　縦＋横で斜め移動\n{turn_keys[0].upper()} で左旋回　／　"
                  f"{turn_keys[1].upper()} で右旋回")
    if MIXED[0] in frames:
        hints += "（移動中も可）"
    tk.Label(root, text=hints + "\nSpace で停止　／　Esc で終了").pack(pady=(0, 16))
    failed = False

    def send(direction):
        nonlocal failed
        if failed:
            return
        if preview is not None:
            preview.write(frames[direction])
        elif port:
            try:
                if port.write(frames[direction]) != len(frames[direction]):
                    raise SerialException("送信が途中で終了しました")
            except (OSError, SerialException):
                failed = True
                port.close()
                status.set("通信断・車体を確認")
                return
        if not guarded:
            status.set(LABELS[direction])

    control = Controller(send, frames, turn_keys)
    send("stop")

    telemetry = bytearray()
    last_report = monotonic()
    names_by_code = list(V3_FRAMES)

    def read_sensors():
        nonlocal last_report
        telemetry.extend(port.read(port.in_waiting))
        while b"\n" in telemetry:
            line, _, tail = telemetry.partition(b"\n")
            telemetry[:] = tail
            if len(line) != 4 or line[0] != ord("!"):
                continue
            try:
                mask, code = int(line[1:2], 16), int(line[2:4], 16)
            except ValueError:
                continue
            if not 0 <= code < len(names_by_code):
                continue
            last_report = monotonic()
            hits = [name for i, name in enumerate(("1 左前", "2 右後ろ", "3 左後ろ", "4 右前"))
                    if mask & (1 << i)]
            sensor_status.set("検知　" + "・".join(hits) if hits else "障害物の検知なし")
            status.set("進行方向を制限" if code == 0 and control.direction != "stop"
                       else LABELS[names_by_code[code]])
        if len(telemetry) > 64:
            telemetry.clear()
        if monotonic() - last_report > 0.6:
            raise SerialException("センサーの状態を受信できません")

    def refresh():
        nonlocal failed
        if not failed:
            if guarded:
                try:
                    read_sensors()
                except (OSError, SerialException):
                    send("stop")
                    failed = True
                    port.close()
                    status.set("通信断・操作終了")
                    sensor_status.set("センサー状態不明")
                    return
            send(control.direction)
            root.after(80, refresh)

    if repeat or preview is not None:
        root.after(80, refresh)
    # フォーカス復帰時、押したままの矢印のキーリピートでは再始動しない。
    virtual_keys = {"Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28, "space": 0x20}
    virtual_keys.update({key: ord(key.upper()) for key in WASD})
    if extended:
        virtual_keys.update({key: ord(key.upper()) for key in turn_keys})
    active = False

    def activate(event):
        nonlocal active
        active = True
        control.keys = {key for key, vk in virtual_keys.items()
                        if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000}
        control.blocked = bool(control.keys)

    def deactivate(event):
        nonlocal active
        active = False
        control.suspend()

    def on_key(event, down):
        if active and not failed:
            control.change(event.keysym, down)

    root.bind("<FocusIn>", activate)
    root.bind("<FocusOut>", deactivate)
    root.bind("<KeyPress>", lambda event: on_key(event, True))
    root.bind("<KeyRelease>", lambda event: on_key(event, False))
    root.bind("<Escape>", lambda event: root.destroy())
    root.after_idle(root.focus_set)
    try:
        root.mainloop()
    finally:
        if port and not failed:
            send("stop")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--profile", type=Path, help="実機用の通信設定 JSON")
    mode.add_argument("--aduc814", action="store_true", help="自作用受信プログラムを識別して操作")
    mode.add_argument("--listen", action="store_true", help="9600 bps で20秒間、起動メッセージを受信")
    parser.add_argument("--port", help="実機のCOMポート（例 COM12）")
    parser.add_argument("--turn-keys", nargs=2, metavar=("LEFT", "RIGHT"),
                        default=("q", "e"), help="左右の旋回キー（英数字各1文字）")
    args = parser.parse_args()
    turn_keys = tuple(k.lower() for k in args.turn_keys)
    if (len(set(turn_keys)) != 2 or
            any(not (len(k) == 1 and k.isascii() and k.isalnum()) for k in turn_keys)):
        parser.error("左右の旋回キーには異なる英数字を1文字ずつ指定してください")
    if not args.profile and not args.aduc814 and not args.listen:
        if args.port:
            parser.error("--port には通信モードの指定が必要です")
        try:
            run_window(turn_keys=turn_keys)
        except OSError as error:
            parser.exit(1, f"シミュレーターを起動できません: {error}\n")
        return
    try:
        baud, frames = read_profile(args.profile) if args.profile else (9600, FRONT1_FRAMES)
        matches = [p.device for p in comports() if (p.vid, p.pid) == (0x10C4, 0xEA60)]
        if not args.port and len(matches) != 1:
            parser.error("CP2102を一意に特定できません。--port で指定してください")
        with Serial(port=None, baudrate=baud, timeout=0.05, write_timeout=0.2) as port:
            port.dtr = port.rts = False
            port.port = args.port or matches[0]
            port.open()
            if args.listen:
                print(f"{port.port} 受信中（9600 bps、20秒、USB送信なし）", flush=True)
                deadline = monotonic() + 20
                received = 0
                while monotonic() < deadline:
                    chunk = port.read(port.in_waiting or 1)
                    if chunk:
                        print(chunk.hex(" "), repr(chunk), flush=True)
                        received += len(chunk)
                print(f"受信終了　{received} バイト")
                return
            if args.aduc814:
                version = await_receiver(port)
                frames = {1: FRONT1_FRAMES, 2: ADUC_FRAMES, 3: V3_FRAMES, 4: V3_FRAMES}[version]
            run_window(port, frames, repeat=args.aduc814, turn_keys=turn_keys,
                       guarded=args.aduc814 and version == 4)
    except (OSError, SerialException, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"実機操作を開始できません: {error}\n")


if __name__ == "__main__":
    main()
