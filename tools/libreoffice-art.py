"""Make the LibreOffice squircles in ../art from Yaru's original sources.

Usage:  python3 tools/libreoffice-art.py

Yaru draws every LibreOffice app as a coloured page with a cut top-right
corner. Here:
- the page's colour and its two light folds (right half, bottom half) are
  carried out to fill the squircle; the cut corner becomes a folded corner
  (a lighter triangle with a soft crease) at Yaru's own cut size, 45 degrees;
- the start centre keeps its grey, and its white page becomes a smaller
  squircle inside it (even grey border) with Yaru's own folded corner;
- every pictogram is Yaru's 256 px drawing at exact proportions.

Yaru's LibreOffice sources hold all sizes in one file, so tools/make-art.py
can't take them directly: the document tile is 64..240 x 44..268, its
background is group g36 and the 256 px pictogram is in the Pictograms layer.
"""
import copy, importlib.util, math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("make_art", HERE / "make-art.py")
ma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ma)

SVG = ma.SVG
INK = ma.INK
X0, Y0, X1, Y1 = 64, 44, 240, 268          # Yaru's document tile (256 px drawing)
A, B = ma.PLATE[0] - ma.EDGE, ma.PLATE[1] + ma.EDGE
SX, SY = (B - A) / (X1 - X0), (B - A) / (Y1 - Y0)
S = min(SX, SY)
TX, TY = A - SX * X0, A - SY * Y0

APPS = {  # icon name in the theme: Yaru source
    "org.libreoffice.LibreOffice.writer": "libreoffice-writer",
    "org.libreoffice.LibreOffice.calc": "libreoffice-calc",
    "org.libreoffice.LibreOffice.impress": "libreoffice-impress",
    "org.libreoffice.LibreOffice.draw": "libreoffice-draw",
    "org.libreoffice.LibreOffice.base": "libreoffice-base",
    "org.libreoffice.LibreOffice.math": "libreoffice-math",
}
MAIN = ("org.libreoffice.LibreOffice.startcenter", "libreoffice-main")

CUT = 116      # the fold line x - y = CUT (source units): Yaru's own cut size
CREASE = 4     # crease width (source units)


def byid(root, i):
    return root.find(f".//*[@id='{i}']")


def squircle(r, c=64.0, n=5.0, steps=240):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        co, si = math.cos(t), math.sin(t)
        pts.append((c + r * math.copysign(abs(co) ** (2 / n), co), c + r * math.copysign(abs(si) ** (2 / n), si)))
    return "M" + " L".join(f"{x:.4f} {y:.4f}" for x, y in pts) + "Z"


def background(root):
    """Squircle-clipped svg with the page colour and folds carried to the edge."""
    o = ET.Element(f"{{{SVG}}}svg", {"viewBox": "0 0 128 128", "width": "128", "height": "128"})
    d = copy.deepcopy(root.find(f"{{{SVG}}}defs"))
    ET.SubElement(d, f"{{{SVG}}}path", {"id": "tq", "d": ma.SQ})
    cp = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "tc"})
    ET.SubElement(cp, f"{{{SVG}}}use", {"href": "#tq"})
    o.append(d)
    clip = ET.SubElement(o, f"{{{SVG}}}g", {"clip-path": "url(#tc)"})
    g = ET.SubElement(clip, f"{{{SVG}}}g", {"transform": f"matrix({SX} 0 0 {SY} {TX} {TY})"})
    big = (X0 - 30, Y0 - 30, X1 + 30, Y1 + 30)
    areas = {"path37": big, "path37-0": big, "path37-6": big,
             "path3": (big[0], 156, big[2], big[3]),       # horizontal fold: bottom half
             "path85": (152, big[1], big[2], big[3])}      # vertical fold: right half
    for e in byid(root, "g36"):
        box = areas.get(e.attrib.get("id"))
        if box:
            x0, y0, x1, y1 = box
            ET.SubElement(g, f"{{{SVG}}}rect", {"x": str(x0), "y": str(y0), "width": str(x1 - x0),
                                                "height": str(y1 - y0), "style": e.attrib.get("style", "")})
    return o, d, clip


def pinned(parent, px, py):
    """Group in source units, uniform scale, with source point (px, py) on the stretched tile."""
    nx, ny = SX * px + TX, SY * py + TY
    return ET.SubElement(parent, f"{{{SVG}}}g", {"transform": f"matrix({S} 0 0 {S} {nx - S * px} {ny - S * py})"})


def coloured(src, out):
    root = ET.parse(src).getroot()
    o, d, clip = background(root)
    fold = byid(root, "path4254")                  # Yaru's faint bottom-right fold
    if fold is not None:
        e = copy.deepcopy(fold)
        e.set("d", "M 170,278 250,198 V 278 Z")    # same triangle, carried past the edge
        pinned(clip, X1, Y1).append(e)
    tr = pinned(clip, X1, Y0)                      # folded top-right corner, 45 degrees
    ET.SubElement(tr, f"{{{SVG}}}path", {"d": f"M {CUT + 24},24 H 260 V {260 - CUT} Z",
                                         "fill": "#ffffff", "opacity": "0.30"})
    c0 = CUT - CREASE
    ET.SubElement(tr, f"{{{SVG}}}path", {"d": f"M {c0 + 24},24 H {CUT + 24} L 260,{260 - CUT} V {260 - c0} Z",
                                         "fill": "#000000", "opacity": "0.15"})
    pic = [c for c in byid(root, "layer6") if c.attrib.get(INK) == "256"][0]
    ux, uy = 64 - S * (X0 + X1) / 2, 64 - S * (Y0 + Y1) / 2
    ug = ET.SubElement(o, f"{{{SVG}}}g", {"transform": f"matrix({S} 0 0 {S} {ux} {uy})"})
    ug.append(copy.deepcopy(pic))
    Path(out).write_bytes(ET.tostring(o))


def main_page(src, out, border=9.0):
    root = ET.parse(src).getroot()
    o, d, clip = background(root)
    r = 56 - border
    top, right = 64 - r, 64 + r
    leg = (224 - 160.89258) * S                    # Yaru's fold, exact size
    c = (right - leg) - top                        # the cut: x - y = c
    cut = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "cut"})
    ET.SubElement(cut, f"{{{SVG}}}path", {"d": f"M -10,-10 H {c - 10} L 138,{138 - c} V 138 H -10 Z"})
    sh = ET.SubElement(o, f"{{{SVG}}}g", {"clip-path": "url(#cut)", "opacity": "0.2"})
    ET.SubElement(sh, f"{{{SVG}}}path", {"d": squircle(r), "transform": "translate(0 1)", "fill": "#000"})
    pg = ET.SubElement(o, f"{{{SVG}}}g", {"clip-path": "url(#cut)"})
    ET.SubElement(pg, f"{{{SVG}}}path", {"d": squircle(r), "fill": byid(root, "path16").attrib.get(
        "style", "").split("fill:")[1].split(";")[0]})
    fg = ET.SubElement(o, f"{{{SVG}}}g", {"transform": f"matrix({S} 0 0 {S} {right - S * 224} {top - S * 60})"})
    fg.append(copy.deepcopy(byid(root, "path28")))   # fold shadow
    fg.append(copy.deepcopy(byid(root, "path20")))   # fold
    Path(out).write_bytes(ET.tostring(o))


if __name__ == "__main__":
    ma.OUT.mkdir(parents=True, exist_ok=True)
    for key, src in APPS.items():
        coloured(ma.fetch(src), ma.OUT / f"{key}.svg")
        print(ma.OUT / f"{key}.svg")
    main_page(ma.fetch(MAIN[1]), ma.OUT / f"{MAIN[0]}.svg")
    print(ma.OUT / f"{MAIN[0]}.svg")
