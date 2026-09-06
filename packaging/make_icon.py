"""Generate packaging/emcomm_bbs.ico (navy tile, amber antenna mast with
radiating arcs). Run once when the artwork changes:  python packaging/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).with_name("emcomm_bbs.ico")
NAVY, AMBER, WHITE = (21, 34, 56, 255), (242, 162, 58, 255), (245, 247, 250, 255)


def render(size):
    s = 8  # supersample for smooth edges
    n = size * s
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, n - 1, n - 1), radius=n * 0.22, fill=NAVY)
    cx, base, top = n / 2, n * 0.84, n * 0.36
    w = max(n * 0.055, s)
    # mast
    d.line((cx, top, cx, base), fill=AMBER, width=int(w))
    d.polygon([(cx - n * 0.16, base), (cx + n * 0.16, base), (cx, base - n * 0.22)], fill=AMBER)
    d.line((cx, top, cx, base), fill=AMBER, width=int(w))
    # feed point
    d.ellipse((cx - n * 0.07, top - n * 0.07, cx + n * 0.07, top + n * 0.07), fill=WHITE)
    # radiating arcs
    for i, r in enumerate((0.16, 0.26, 0.36)):
        box = (cx - n * r, top - n * r, cx + n * r, top + n * r)
        width = int(max(n * 0.04, s))
        d.arc(box, start=200, end=250, fill=WHITE, width=width)
        d.arc(box, start=290, end=340, fill=WHITE, width=width)
    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [render(sz) for sz in sizes]
    frames[0].save(OUT, format="ICO", sizes=[(sz, sz) for sz in sizes], append_images=frames[1:])
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
