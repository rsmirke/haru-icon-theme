"""Squircle versions of non-Yaru app icons (the app's own SVG).

Same idea as make-art.py, for icons that do not come from Yaru: every
top-level element of the app's SVG is either
  stretch  - background, reshaped so the tile covers the squircle,
  uniform  - pictogram, exact proportions, about the tile centre,
  fill     - replaced by a rectangle of its own fill reaching the tile edge,
  drop     - left out (e.g. the tile's own shadow or housing).
Elements are addressed by their index among the drawable top-level children
(of the first <g> when the drawing is wrapped in one).

Usage: python3 tools/own-art.py [--out DIR] [name ...]
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ma", HERE / "make-art.py")
ma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ma)
SVG, SQ, render_bbox = ma.SVG, ma.SQ, ma.render_bbox

MANIFEST = Path.home() / ".local/share/haru/manifest.json"
NONDRAW = {"defs", "metadata", "namedview", "title", "linearGradient", "radialGradient", "mask",
           "clipPath", "filter", "style"}

# tile = the app's own tile/base in its 128 px drawing (x0, y0, x1, y1)
ICONS = {
    # the keyboard's white body fills the squircle (its old bottom lip is dropped); keys unchanged
    "org.gnome.gitlab.somas.Apostrophe": dict(tile=(8, 28, 120, 112), fill={1}, drop={0}, scale=0.9),
    # the stall's wood fills the squircle, the awning runs across the top; fruit unchanged
    "io.github.kolunmi.Bazaar": dict(tile=(4, 12, 124, 112), fill={3}, drop={0, 1},
                                     stretch={2, 4, 5, 6, 7, 13, 14, 15, 16, 17, 18, 19, 20},
                                     scale=0.86, offset=(0, 6)),
    # the diamond's green-to-blue field fills the squircle; the white facets unchanged
    "org.gnome.Adwaita1.Demo": dict(tile=(9, 8, 119, 119), fill={0}, drop={4}, scale=0.95),
    "org.gnome.design.AppIconPreview": dict(tile=(8, 28, 120, 112), stretch={1, 2, 3, 5, 6}, drop={0, 4},
                                            scale=0.82, offset=(0, 13)),
    "io.gitlab.metadatacleaner.metadatacleaner": dict(tile=(20, 5, 108, 113), fill={1}, drop={0}, stretch={3}, scale=0.84,
                                                      offset=(0, -7)),
    "com.github.johnfactotum.Foliate": dict(tile=(8, 21, 120, 110), stretch=set(range(0, 17)), scale=0.9,
                                            offset=(0, 6)),
    # the gauge's light housing becomes the squircle; dial, needle and buttons unchanged
    # the card's grey gradient and shine fill the squircle (its black outline is dropped); stars unchanged.
    # Brand icon: built on your own machine only, into ~/.config/haru/art (see config.user.toml)
    "net.ankiweb.Anki": dict(tile=(6, 2.5, 27, 30.5), stretch={1, 5}, drop={0}),
    "org.gnome.Resources": dict(tile=(12, 20, 116, 124), fill={1}, drop={0}, scale=0.8, offset=(0, -1)),
}


def tag(e):
    return e.tag.split("}")[1]


def compose(name, cfg, src, out):
    root = ET.parse(src).getroot()
    holder = root
    drawable = [c for c in root if tag(c) not in NONDRAW]
    hold_ts = []
    while len(drawable) == 1 and tag(drawable[0]) == "g" and cfg.get("unwrap", True):
        holder = drawable[0]
        hold_ts.append(holder.attrib.get("transform", ""))
        drawable = [c for c in holder if tag(c) not in NONDRAW]
    defs = ET.Element(f"{{{SVG}}}defs")
    for c in root.iter():
        if tag(c) in NONDRAW - {"metadata", "namedview", "title", "style"} and c is not root:
            if tag(c) == "defs":
                for cc in c:
                    defs.append(copy.deepcopy(cc))
            elif c not in list(defs):
                defs.append(copy.deepcopy(c))
    x0, y0, x1, y1 = cfg["tile"]
    a, b = 6, 122
    sx, sy = (b - a) / (x1 - x0), (b - a) / (y1 - y0)
    tx, ty = a - sx * x0, a - sy * y0
    s = min(sx, sy) * cfg.get("scale", 1.0)            # optional: pictograms a bit smaller
    ox, oy = cfg.get("offset", (0, 0))                  # optional: nudge pictograms (output px)
    ux, uy = 64 - s * (x0 + x1) / 2 + ox, 64 - s * (y0 + y1) / 2 + oy
    hold_t = " ".join(t for t in hold_ts if t)      # transforms of the groups we stepped into

    out_svg = ET.Element(f"{{{SVG}}}svg", {"viewBox": "0 0 128 128", "width": "128", "height": "128"})
    d = copy.deepcopy(defs)
    ET.SubElement(d, f"{{{SVG}}}path", {"id": "tq", "d": SQ})
    cp = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "tc"})
    ET.SubElement(cp, f"{{{SVG}}}use", {"href": "#tq"})
    out_svg.append(d)
    bbox_defs = defs
    for i, e in enumerate(drawable):
        if i in cfg.get("drop", ()):
            continue
        if i in cfg.get("fill", ()):
            bb = render_bbox(bbox_defs, e, cfg["tile"])
            fill = e.attrib.get("fill") or dict(kv.split(":", 1) for kv in e.attrib.get("style", "").split(";")
                                                 if ":" in kv).get("fill", "#000")
            g = ET.SubElement(out_svg, f"{{{SVG}}}g", {"clip-path": "url(#tc)"})
            ET.SubElement(g, f"{{{SVG}}}rect", {"x": "0", "y": "0", "width": "128", "height": "128",
                                                "fill": fill})
            continue
        if i in cfg.get("stretch", ()):
            g = ET.SubElement(out_svg, f"{{{SVG}}}g", {"clip-path": "url(#tc)"})
            g = ET.SubElement(g, f"{{{SVG}}}g", {"transform": f"matrix({sx} 0 0 {sy} {tx} {ty}) {hold_t}"})
        else:
            g = ET.SubElement(out_svg, f"{{{SVG}}}g", {"transform": f"matrix({s} 0 0 {s} {ux} {uy}) {hold_t}"})
        g.append(copy.deepcopy(e))
    path = Path(out) / f"{name}.svg"
    path.write_bytes(ET.tostring(out_svg))
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    out = HERE.parent / "art"
    if args[:1] == ["--out"]:
        out, args = Path(args[1]), args[2:]
    Path(out).mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for name in args or list(ICONS):
        print(compose(name, ICONS[name], manifest[name].get("orig_src") or manifest[name]["src"], out))
