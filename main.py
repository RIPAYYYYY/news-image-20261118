#!/usr/bin/env python3
"""news-image-20261118 -- "Sum up 18 November's world news in one image".

A self-contained, deterministic newspaper-poster renderer.
Standard library only. Draws a 1024x1024 front page for
Wednesday 18 November 2026 into $MAKEFUN_OUTPUT_DIR/entry.png
(default output dir: /output).

Everything is drawn from code: a hand-authored 5x7 bitmap font,
geometric icon scenes, and a from-scratch PNG encoder (zlib/struct).
No randomness, no clocks, no network -- two runs are byte-identical.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (246, 241, 230)
INK = (20, 22, 28)
RED = (176, 32, 38)
NAVY = (23, 43, 77)
NAVY_LT = (46, 74, 120)
WHITE = (255, 255, 255)
GOLD = (198, 148, 44)
GREEN = (52, 120, 62)
SKY = (120, 168, 205)
ORANGE = (226, 110, 40)

# ---------------------------------------------------------------- font
# Hand-authored 5x7 bitmap font. Each glyph: 7 rows of 5 pixels.
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#", "...#", "...#", "...#", "#..#", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", ".#.#.", "..#..", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"],
    "3": [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ",": [".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    "'": [".##..", ".##..", "..#..", ".....", ".....", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
}


# ---------------------------------------------------------------- canvas
class Canvas:
    """A flat RGB pixel buffer with hand-rolled drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def frame(self, x, y, w, h, t, color):
        self.rect(x, y, w, t, color)
        self.rect(x, y + h - t, w, t, color)
        self.rect(x, y, t, h, color)
        self.rect(x + w - t, y, t, h, color)

    def disc(self, cx, cy, r, color):
        r2 = r * r
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            span = int(math.sqrt(max(0, r2 - dy * dy)))
            self.rect(cx - span, yy, 2 * span + 1, 1, color)

    def ellipse(self, cx, cy, rx, ry, color):
        if rx <= 0 or ry <= 0:
            return
        for yy in range(cy - ry, cy + ry + 1):
            t = (yy - cy) / ry
            span = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.rect(cx - span, yy, 2 * span + 1, 1, color)

    def ring(self, cx, cy, r, t, color):
        """Thick circle outline, stamped parametrically."""
        steps = max(24, int(2 * math.pi * r))
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            self.disc(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)),
                      t, color)

    def ellipse_line(self, cx, cy, rx, ry, t, color, rot=0.0):
        """Thin ellipse outline (optionally rotated), stamped."""
        if rx <= 0 or ry <= 0:
            return
        steps = max(24, int(2 * math.pi * max(rx, ry)))
        cr = math.cos(rot)
        sr = math.sin(rot)
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            ex = rx * math.cos(a)
            ey = ry * math.sin(a)
            x = cx + ex * cr - ey * sr
            y = cy + ex * sr + ey * cr
            self.disc(int(x), int(y), t, color)

    def line(self, x0, y0, x1, y1, t, color):
        """Thick line: stamp discs along the segment."""
        dist = max(abs(x1 - x0), abs(y1 - y0), 1)
        steps = int(dist)
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i / steps
            y = y0 + (y1 - y0) * i / steps
            self.disc(int(x), int(y), t, color)

    def poly(self, pts, color):
        """Filled polygon via scanline even-odd fill."""
        ys = [p[1] for p in pts]
        y_lo = max(0, int(min(ys)))
        y_hi = min(self.h - 1, int(max(ys)))
        n = len(pts)
        for yy in range(y_lo, y_hi + 1):
            nodes = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    nodes.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
            nodes.sort()
            for i in range(0, len(nodes) - 1, 2):
                xa = int(nodes[i])
                xb = int(nodes[i + 1])
                self.rect(xa, yy, xb - xa + 1, 1, color)


# ---------------------------------------------------------------- text
def text_width(s, scale):
    if not s:
        return 0
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    """Draw string with top-left at (x, y). Glyph cell: 6*scale wide."""
    for ch in s.upper():
        glyph = FONT.get(ch, FONT[" "])
        for gy, row in enumerate(glyph):
            for gx, cell in enumerate(row):
                if cell == "#":
                    cv.rect(x + gx * scale, y + gy * scale, scale, scale,
                            color)
        x += 6 * scale
    return x


def draw_text_c(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_width(s, scale) // 2, y, s, scale, color)


# ---------------------------------------------------------------- icons
def icon_globe(cv, cx, cy, r):
    col = PAPER
    cv.ring(cx, cy, r, 3, col)
    for frac in (0.38, 0.72):
        cv.ellipse_line(cx, cy, int(r * frac), r, 2, col)
    cv.line(cx, cy - r, cx, cy + r, 2, col)
    for frac in (-0.48, 0.0, 0.48):
        dy = int(r * frac)
        half = int(math.sqrt(max(0, r * r - dy * dy)))
        cv.line(cx - half, cy + dy, cx + half, cy + dy, 2, col)
    # orbit ring with a small satellite dot
    cv.ellipse_line(cx, cy, r + 30, int((r + 30) * 0.34), 3, RED, rot=-0.32)
    a = -0.32
    sx = cx + int((r + 30) * math.cos(2.4) * math.cos(a)
                  - (r + 30) * 0.34 * math.sin(2.4) * math.sin(a))
    sy = cy + int((r + 30) * math.cos(2.4) * math.sin(a)
                  + (r + 30) * 0.34 * math.sin(2.4) * math.cos(a))
    cv.disc(sx, sy, 6, GOLD)


def icon_plane(cv, cx, cy):
    for i in range(3):  # speed lines
        yy = cy - 12 + i * 12
        cv.line(cx - 98, yy, cx - 76, yy, 3, SKY)
    cv.rect(cx - 54, cy - 7, 92, 15, INK)
    cv.poly([(cx + 38, cy - 7), (cx + 38, cy + 8), (cx + 56, cy + 1)], INK)
    cv.poly([(cx - 10, cy + 6), (cx + 14, cy + 6), (cx + 1, cy + 29)], INK)
    cv.poly([(cx - 52, cy - 6), (cx - 34, cy - 6), (cx - 40, cy - 27)],
            INK)
    cv.poly([(cx - 52, cy + 6), (cx - 38, cy + 6), (cx - 42, cy + 18)],
            INK)
    cv.disc(cx + 28, cy - 2, 3, PAPER)  # cockpit window
    for i in range(5):
        cv.disc(cx - 26 + i * 12, cy + 1, 2, PAPER)


def icon_bridge(cv, cx, cy):
    cv.rect(cx - 62, cy - 40, 10, 50, INK)
    cv.rect(cx + 52, cy - 40, 10, 50, INK)
    cv.line(cx - 57, cy - 38, cx - 97, cy + 4, 3, INK)
    cv.line(cx + 57, cy - 38, cx + 97, cy + 4, 3, INK)
    cv.line(cx - 57, cy - 38, cx, cy + 4, 3, INK)
    cv.line(cx + 57, cy - 38, cx, cy + 4, 3, INK)
    cv.rect(cx - 98, cy + 2, 196, 7, INK)
    for i in range(9):  # red burst where the strike hit
        a = 2 * math.pi * i / 9
        cv.line(cx + int(5 * math.cos(a)), cy - 4 + int(5 * math.sin(a)),
                cx + int(15 * math.cos(a)), cy - 4 + int(15 * math.sin(a)),
                3, RED)
    cv.disc(cx, cy - 4, 5, RED)
    for k in range(2):  # water
        yy = cy + 22 + k * 11
        for xx in range(cx - 92, cx + 92, 8):
            cv.disc(xx, yy + int(3 * math.sin(xx * 0.11 + k * 2.0)), 2, SKY)


def icon_drone(cv, cx, cy):
    for dx, dy in ((-46, -22), (46, -22), (-46, 22), (46, 22)):
        cv.line(cx, cy, cx + dx, cy + dy, 3, INK)
        cv.ring(cx + dx, cy + dy, 11, 2, INK)
        cv.disc(cx + dx, cy + dy, 2, INK)
    cv.rect(cx - 17, cy - 10, 34, 20, INK)
    cv.disc(cx, cy + 17, 5, RED)
    cv.line(cx - 10, cy + 10, cx - 14, cy + 20, 3, INK)
    cv.line(cx + 10, cy + 10, cx + 14, cy + 20, 3, INK)


def icon_dove(cv, cx, cy):
    cv.poly([(cx - 38, cy - 2), (cx - 68, cy - 14), (cx - 62, cy + 2),
             (cx - 70, cy + 12), (cx - 40, cy + 12)], NAVY)
    cv.ellipse(cx - 2, cy + 3, 42, 17, NAVY)
    cv.poly([(cx - 18, cy + 1), (cx + 8, cy - 30), (cx + 20, cy + 3)],
            NAVY_LT)
    cv.disc(cx + 36, cy - 13, 12, NAVY)
    cv.poly([(cx + 46, cy - 15), (cx + 62, cy - 10), (cx + 46, cy - 5)],
            GOLD)
    cv.disc(cx + 39, cy - 15, 2, PAPER)
    cv.line(cx + 54, cy - 4, cx + 34, cy + 14, 2, GREEN)
    for t in (0.3, 0.55, 0.8):
        lx = int(cx + 54 - 20 * t)
        ly = int(cy - 4 + 18 * t)
        cv.ellipse(lx, ly - 4, 6, 3, GREEN)
        cv.ellipse(lx - 3, ly + 3, 6, 3, GREEN)


def icon_chip(cv, cx, cy):
    bx, by = cx - 58, cy - 27
    for i in range(3):
        off = 12 + i * 16
        cv.rect(bx - 9, by + off, 9, 5, INK)
        cv.rect(bx + 56, by + off, 9, 5, INK)
        cv.rect(bx + off, by - 9, 5, 9, INK)
        cv.rect(bx + off, by + 54, 5, 9, INK)
    cv.rect(bx, by, 56, 54, INK)
    cv.rect(bx + 11, by + 11, 34, 32, PAPER)
    cv.rect(bx + 19, by + 19, 18, 16, RED)
    pts = [(cx + 18, cy + 22), (cx + 38, cy + 6), (cx + 50, cy + 13),
           (cx + 74, cy - 20)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 4, RED)
    cv.poly([(cx + 76, cy - 22), (cx + 59, cy - 19), (cx + 71, cy - 3)],
            RED)


def icon_missile(cv, cx, cy):
    dx, dy = 0.7071, -0.7071   # axis: up-right
    px_, py_ = 0.7071, 0.7071  # perpendicular
    tip = (cx + 54 * dx, cy + 54 * dy)
    base = (cx - 38 * dx, cy - 38 * dy)
    c1 = (base[0] + 11 * px_, base[1] + 11 * py_)
    c2 = (base[0] - 11 * px_, base[1] - 11 * py_)
    cv.poly([tip, c1, c2], INK)
    cv.disc(int(tip[0] - 16 * dx), int(tip[1] - 16 * dy), 5, RED)
    fbase = (cx - 26 * dx, cy - 26 * dy)
    cv.poly([(fbase[0], fbase[1]),
             (fbase[0] + 26 * px_, fbase[1] + 26 * py_),
             (base[0] + 6 * px_, base[1] + 6 * py_)], NAVY)
    cv.poly([(fbase[0], fbase[1]),
             (fbase[0] - 26 * px_, fbase[1] - 26 * py_),
             (base[0] - 6 * px_, base[1] - 6 * py_)], NAVY)
    flame = (cx - 58 * dx, cy - 58 * dy)
    cv.poly([(base[0] + 6 * px_, base[1] + 6 * py_),
             (base[0] - 6 * px_, base[1] - 6 * py_), flame], ORANGE)
    for i in range(6):  # dotted trajectory
        t = i / 5.0
        qx = cx - 96 + 62 * t
        qy = cy + 44 - 66 * t + 26 * t * t
        cv.disc(int(qx), int(qy), 3, SKY)


# ---------------------------------------------------------------- layout
def panel(cv, x, y, w, h, icon, lines):
    cv.rect(x, y, w, h, WHITE)
    cv.frame(x, y, w, h, 3, INK)
    icon(cv, x + w // 2, y + 46)
    ly = y + 94
    for ln in lines:
        draw_text_c(cv, x + w // 2, ly, ln, 4, INK)
        ly += 36


def compose():
    cv = Canvas(W, H, PAPER)

    # masthead
    draw_text_c(cv, W // 2, 30, "THE WORLD TODAY", 10, INK)
    cv.rect(40, 114, 944, 5, RED)

    # date band
    cv.rect(40, 134, 944, 62, RED)
    draw_text_c(cv, W // 2, 147, "WEDNESDAY 18 NOVEMBER 2026", 5, WHITE)

    # lead story: APEC summit in Shenzhen
    cv.rect(40, 216, 944, 242, NAVY)
    cv.frame(40, 216, 944, 242, 4, INK)
    icon_globe(cv, 216, 337, 90)
    draw_text(cv, 356, 244, "APEC SUMMIT", 8, PAPER)
    draw_text(cv, 356, 312, "OPENS IN SHENZHEN", 6, PAPER)
    cv.rect(358, 372, 210, 5, RED)
    draw_text(cv, 356, 388, "LEADERS OF 21 PACIFIC ECONOMIES", 3, PAPER)
    draw_text(cv, 356, 416, "GATHER IN CHINA", 3, GOLD)

    # story grid
    cols = [40, 361, 683]
    widths = [301, 302, 301]
    row1 = [
        (icon_plane, ["TRUMP IN", "MANILA FOR", "QUAD TALKS"]),
        (icon_bridge, ["UKRAINE", "HITS CRIMEA", "BRIDGE"]),
        (icon_drone, ["DRONES OVER", "THE GULF", "OIL AT $93"]),
    ]
    row2 = [
        (icon_dove, ["GAZA TRUCE", "NEAR", "COLLAPSE"]),
        (icon_chip, ["NVIDIA", "BEATS", "FORECASTS"]),
        (icon_missile, ["NORTH KOREA", "FIRES", "MISSILES"]),
    ]
    for row, yy in ((row1, 474), (row2, 698)):
        for (icon, lines), xx, ww in zip(row, cols, widths):
            panel(cv, xx, yy, ww, 208, icon, lines)

    # footer strips
    for fx, fw in ((40, 462), (522, 462)):
        cv.rect(fx, 922, fw, 64, NAVY)
    draw_text_c(cv, 40 + 231, 932, "CYCLONE AKVAN", 3, PAPER)
    draw_text_c(cv, 40 + 231, 958, "NEARS INDIA COAST", 3, GOLD)
    draw_text_c(cv, 522 + 231, 932, "VOYAGER 1 NEARS", 3, PAPER)
    draw_text_c(cv, 522 + 231, 958, "ONE LIGHT-DAY AWAY", 3, GOLD)

    return cv


# ---------------------------------------------------------------- PNG out
def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.px[yy * stride:(yy + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    cv = compose()
    n = write_png(cv, os.path.join(outdir, "entry.png"))
    print("wrote entry.png (%d bytes)" % n)


if __name__ == "__main__":
    main()
