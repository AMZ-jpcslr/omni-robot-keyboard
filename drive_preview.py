"""A top view driven by the output of the compiled ADuC814 receiver logic."""

from pathlib import Path
from time import monotonic
from math import cos, sin
import tkinter as tk


class DrivePreview:
    WIDTH = 520
    HEIGHT = 320
    VELOCITY = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0),
                (-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0), (0, 0))

    def __init__(self, root):
        import pywasm

        library = Path(__file__).resolve().parent / "preview" / "receiver.wasm"
        self.runtime = pywasm.Runtime()
        self.module = self.runtime.instance_from_file(str(library))
        self.clock = monotonic()
        self.x = self.WIDTH / 2
        self.y = self.HEIGHT / 2
        self.heading = 0.0
        canvas = self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT,
                                         background="#ecf2f1", highlightthickness=0)
        canvas.pack(padx=16, pady=(8, 0))
        for x in range(20, self.WIDTH, 32):
            for y in range(16, self.HEIGHT, 32):
                canvas.create_oval(x-1, y-1, x+1, y+1, fill="#bbc9c6", outline="")
        self.parts = []

        def polygon(points, color):
            item = canvas.create_polygon(*points, fill=color, outline="", tags="chassis")
            self.parts.append((item, points))

        for x in (-14, 14):
            for y in (-13, 13):
                polygon((x-5,y-7, x+5,y-7, x+5,y+7, x-5,y+7), "#253735")
        polygon((-14,-16, 14,-16, 14,16, -14,16), "#197668")
        polygon((0,-11, -7,4, 0,1, 7,4), "white")
        self.draw()
        self.animate()

    def draw(self):
        c, s = cos(self.heading), sin(self.heading)
        for item, points in self.parts:
            coords = []
            for x, y in zip(points[::2], points[1::2]):
                coords.extend((self.x + c*x - s*y, self.y + s*x + c*y))
            self.canvas.coords(item, *coords)

    def advance(self):
        now = monotonic()
        ticks = int((now - self.clock) / 0.01)
        self.clock += ticks * 0.01
        previous = self.x, self.y, self.heading
        # After 25 ticks without a frame the C receiver has already stopped.
        for _ in range(min(ticks, 25)):
            code, = self.runtime.invocate(self.module, "preview_direction", [])
            move = code
            turn = 0
            scale = 1.0
            if code >= 11:
                move = 1 + (code - 11) % 8
                turn = -1 if code < 19 else 1
                scale = 0.5
            elif code in (9, 10):
                turn = -1 if code == 9 else 1
            dx, dy = self.VELOCITY[move]
            dx *= scale
            dy *= scale
            self.heading += 0.018 * turn * scale
            c, s = cos(self.heading), sin(self.heading)
            self.x = min(max(self.x + 1.4*(c*dx - s*dy), 28), self.WIDTH - 28)
            self.y = min(max(self.y + 1.4*(s*dx + c*dy), 28), self.HEIGHT - 28)
            self.runtime.invocate(self.module, "receiver_tick_10ms", [])
        if previous != (self.x, self.y, self.heading):
            self.draw()

    def write(self, frame):
        self.advance()
        for byte in frame:
            self.runtime.invocate(self.module, "receiver_byte", [byte])

    def animate(self):
        self.advance()
        self.canvas.after(16, self.animate)
