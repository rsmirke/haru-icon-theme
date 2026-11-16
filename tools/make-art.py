"""Make the "fills the squircle" artwork in ../art from Yaru's original sources.

Usage:  python3 tools/make-art.py [icon-name ...]

Yaru's source SVGs (CC BY-SA 4.0, https://github.com/ubuntu/yaru) are
downloaded into tools/yaru-src/ the first time.


Background art is stretched (non-uniformly) so the original tile covers the
squircle; pictograms keep Yaru's exact proportions (uniform scale); small
repeated details (film holes, sun) keep their shape and only move.
Tile shadows, borders and edge highlights are dropped (the squircle has its
own rim)."""
import copy, io, json, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
from PIL import Image

SVG = "http://www.w3.org/2000/svg"
INK = "{http://www.inkscape.org/namespaces/inkscape}label"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd")

HERE = Path(__file__).resolve().parent
SRC = HERE / "yaru-src"
OUT = HERE.parent / "art"
RAW = "https://raw.githubusercontent.com/ubuntu/yaru/master/icons/src/fullcolor/default/apps/"


def squircle_path(n=5.0, r=56.0, c=64.0, steps=96):
    import math
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        co, si = math.cos(t), math.sin(t)
        pts.append((c + r * math.copysign(abs(co) ** (2 / n), co), c + r * math.copysign(abs(si) ** (2 / n), si)))
    return "M" + " L".join(f"{x:.5f} {y:.5f}" for x, y in pts) + "Z"


SQ = squircle_path()


def fetch(name, srcdir="apps"):
    SRC.mkdir(exist_ok=True)
    path = SRC / f"{name}.svg"
    if not path.exists():
        import urllib.request
        with urllib.request.urlopen(RAW.replace("/apps/", f"/{srcdir}/") + f"{name}.svg", timeout=30) as r:
            path.write_bytes(r.read())
    return path

PORTRAIT = (64, 44, 240, 268)
LANDSCAPE = (40, 68, 264, 244)

# key = the icon name in the theme ("name@variant" = an alternative, not built by default)
ICONS = {
    "org.gnome.Contacts": dict(src="address-book-app", tile=PORTRAIT,
                               stretch={"rect4362", "rect4287", "rect4289", "rect4327", "rect1609"}),
    "org.gnome.Ptyxis": dict(src="terminal-app2", tile=LANDSCAPE, drop={"rect4158-78"}),
    "haru-snap-store_snap-store": dict(src="app-center", tile=PORTRAIT,
                                                fill_rect={"rect4158"},
                                                drop={"rect4158-2", "rect4158-2-7"},
                                                extra=("path4-2", "path4"),
                                                shrink=({"path1052-7", "path1052-7-3", "text954-5", "rect1040",
                                                         "path1693", "rect4270", "rect4272"}, 0.88),
                                                keep={"path1052-7", "path1052-7-3", "text954-5",
                                                      "rect1040", "path1693", "rect4270", "rect4272"}),
    "org.gnome.SimpleScan": dict(src="scanner", tile=PORTRAIT, drop={"path931"},
                                          stretch={"path1328", "path1326", "path1324", "path1322", "path1320",
                                                   "path1318", "path1316", "path1314", "path1312", "path1032",
                                                   "rect1157", "rect1157-3", "rect1157-3-3", "rect4158-8"}),
    "nvidia-settings": dict(src="nvidia-settings", tile=LANDSCAPE, stretch={"path1027"}),
    "org.gnome.Logs": dict(src="log-viewer-app", tile=PORTRAIT, drop={"path931"},
                                    stretch={'path5674', 'path5672', 'path1032', 'path5682', 'path5676', 'path5680', 'path5670', 'path5686', 'path5684', 'path5678'},
                                    place={'rect5135-76', 'rect5135-4', 'rect5135-88-3', 'rect5135-8', 'rect5135-5-6', 'rect5135-73', 'rect5135', 'rect5135-73-2', 'rect5135-7', 'rect5135-71-4', 'rect5135-71', 'rect5135-2', 'rect5135-0', 'rect5135-9', 'rect5135-88', 'rect5135-76-2', 'rect5135-2-3', 'rect5135-89', 'rect5135-3-0', 'rect5135-0-1', 'rect5135-5', 'rect5135-7-7', 'rect5135-3', 'rect5135-4-7', 'rect5135-8-1', 'rect5135-89-9'}),
    "org.gnome.DiskUtility": dict(src="disk-utility-app", tile=PORTRAIT, drop={"path931"},
                                          place={"path2571", "path2569", "circle1473"}),
    "preferences-desktop-locale": dict(src="preferences-desktop-locale", tile=LANDSCAPE,
                                       srcdir="categories"),
    "org.gnome.Yelp": dict(src="help-app", tile=(40, 44, 264, 268), fill_rect={"path11042", "rect12119"},
                     drop={"path11042-5"}),
    "org.gnome.DejaDup": dict(src="backups-app", tile=PORTRAIT, drop={"rect4158-96", "rect4158-96-2"},
                                   door=dict(box=(64.0, 64.0, 47.5, 49.7), fill="#3b3b3b", bevel=1.0)),
    "org.gnome.Maps": dict(src="maps-app", tile=LANDSCAPE),
    "org.gnome.TextEditor": dict(src="org.gnome.TextEditor", tile=PORTRAIT,
                        stretch={"path4633", "rect9031"}, drop={"path931"}),
    "org.gnome.Papers": dict(src="papers", tile=PORTRAIT,
                            stretch={"path4633", "path4725", "path4631", "path4635", "path4727", "path14983",
                                     "path11", "rect4158-0-3"}),
    "org.gnome.Loupe": dict(src="org.gnome.Loupe", tile=LANDSCAPE,
                         stretch={"path1031-0", "path4390-7", "rect4248-4", "path4266-2", "path1051-6",
                                  "path4244-2-5", "path4246-6-2"},
                         place={"circle967-5", "path1076-1"}),
    "org.gnome.Showtime": dict(src="org.gnome.Showtime", tile=LANDSCAPE,
                         place={"path18274", "path18272", "path18270", "path13702", "path13698", "path13696",
                                "path13694", "path13692", "path13690", "path13688", "path13686", "path13684",
                                "path13682", "path13680"}),
    "org.gnome.DejaDup@yaru-door": dict(src="backups-app", tile=PORTRAIT),
}

EDGE = 2.0          # how far the tile edge goes past the squircle (in 128-px units)
PLATE = (8, 120)


def style_of(e):
    return dict(kv.split(":", 1) for kv in e.attrib.get("style", "").split(";") if ":" in kv)


def is_tile_shadow(e):
    st = style_of(e)
    fill = st.get("fill", e.attrib.get("fill", ""))
    try:
        op = float(st.get("opacity", "1"))
    except ValueError:
        op = 1
    return fill == "none" or (fill == "#000000" and op <= 0.2)


def render_bbox(defs, elem, tile, scale=4):
    """Bounding box (source units) of one element, found by rendering it."""
    x0, y0, x1, y1 = tile
    pad = 40
    vb = (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)
    root = ET.Element(f"{{{SVG}}}svg", {"viewBox": " ".join(map(str, vb)),
                                         "width": str(vb[2] * scale), "height": str(vb[3] * scale)})
    root.append(copy.deepcopy(defs))
    root.append(copy.deepcopy(elem))
    data = ET.tostring(root)
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pb = loader.get_pixbuf()
    im = Image.frombuffer("RGBA", (pb.get_width(), pb.get_height()), pb.get_pixels(), "raw", "RGBA",
                          pb.get_rowstride(), 1)
    bb = im.getchannel("A").point(lambda a: 255 if a > 4 else 0).getbbox()
    if not bb:
        return None
    return (vb[0] + bb[0] / scale, vb[1] + bb[1] / scale, vb[0] + bb[2] / scale, vb[1] + bb[3] / scale)


def compose(key, cfg):
    tree = ET.parse(fetch(cfg["src"], cfg.get("srcdir", "apps")))
    root = tree.getroot()
    defs = root.find(f"{{{SVG}}}defs")
    icon = [c for c in root if c.tag == f"{{{SVG}}}g"][0]
    x0, y0, x1, y1 = cfg["tile"]
    a, b = PLATE[0] - EDGE, PLATE[1] + EDGE
    sx, sy = (b - a) / (x1 - x0), (b - a) / (y1 - y0)
    tx, ty = a - sx * x0, a - sy * y0
    s = min(sx, sy)
    tcx, tcy = (x0 + x1) / 2, (y0 + y1) / 2
    ux, uy = 64 - s * tcx, 64 - s * tcy

    stretch, uniform, places, corners, fills, underlays = [], [], [], [], [], []
    for layer in icon:
        name = layer.attrib.get(INK, "")
        if name in ("Baseplate", "Borders", "Highlights", "Shadow", "Optional outline for white icons"):
            continue
        for e in list(layer):
            eid = e.attrib.get("id", "")
            if eid in cfg.get("drop", set()):
                continue
            if cfg.get("underlay") and eid == cfg["underlay"][0]:
                underlays.append(e)
                continue
            if eid in cfg.get("fill_rect", set()):
                fills.append(e)
                continue
            if eid in cfg.get("keep", set()):      # background-layer pictogram: exact proportions
                uniform.append(e)
                continue
            if name == "Backgrounds" and eid not in cfg.get("corner", set()):
                if is_tile_shadow(e):
                    continue
                stretch.append(e)
            elif eid in cfg.get("stretch", set()):
                stretch.append(e)
            elif eid in cfg.get("place", set()):
                places.append(e)
            elif eid in cfg.get("corner", set()):
                corners.append(e)
            else:
                uniform.append(e)

    # pictogram pieces that live outside the main icon group (App Centre's handle)
    for eid in cfg.get("extra", ()):
        found = [x for x in root.iter() if x.attrib.get("id") == eid]
        uniform.extend(found)

    out = ET.Element(f"{{{SVG}}}svg", {"viewBox": "0 0 128 128", "width": "128", "height": "128"})
    d = copy.deepcopy(defs)
    ET.SubElement(d, f"{{{SVG}}}path", {"id": "tq", "d": SQ})
    cp = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "tc"})
    ET.SubElement(cp, f"{{{SVG}}}use", {"href": "#tq"})
    out.append(d)

    clip = ET.SubElement(out, f"{{{SVG}}}g", {"clip-path": "url(#tc)"})
    g = ET.SubElement(clip, f"{{{SVG}}}g", {"transform": f"matrix({sx} 0 0 {sy} {tx} {ty})"})
    fill_g = ET.SubElement(g, f"{{{SVG}}}g")
    # an element that only shows through a hole in the art (App Centre's handle)
    for e in underlays:
        bx0, by0, bx1, by1 = cfg["underlay"][1]
        ucp = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "under"})
        ET.SubElement(ucp, f"{{{SVG}}}rect", {"x": str(bx0), "y": str(by0), "width": str(bx1 - bx0),
                                              "height": str(by1 - by0)})
        ug0 = ET.SubElement(g, f"{{{SVG}}}g", {"clip-path": "url(#under)"})
        ug0.append(copy.deepcopy(e))
    for e in stretch:
        g.append(copy.deepcopy(e))
    # round shapes (circles, arcs) become rectangles reaching the tile edge,
    # keeping their exact fill, so the colour field fills the squircle
    for e in fills:
        bb = render_bbox(defs, e, cfg["tile"])
        if not bb:
            continue
        near = 6
        rx0 = x0 - 20 if bb[0] - x0 < near else bb[0]
        ry0 = y0 - 20 if bb[1] - y0 < near else bb[1]
        rx1 = x1 + 20 if x1 - bb[2] < near else bb[2]
        ry1 = y1 + 20 if y1 - bb[3] < near else bb[3]
        attrs = {k: v for k, v in e.attrib.items() if k in ("style", "fill", "opacity", "fill-opacity")}
        st = dict(kv.split(":", 1) for kv in attrs.get("style", "").split(";") if ":" in kv)
        st.pop("stroke", None)
        attrs["style"] = ";".join(f"{k}:{v}" for k, v in st.items())
        ET.SubElement(fill_g, f"{{{SVG}}}rect", dict(attrs, x=str(rx0), y=str(ry0), width=str(rx1 - rx0),
                                                height=str(ry1 - ry0)))
    door = cfg.get("door")
    if door:
        # Yaru's safe door is a thin dark seam (not a filled panel) with a faint
        # light edge inside at the top and outside at the bottom; same here,
        # but with a squircle outline.
        cx, cy, hw, hh = door["box"]
        w = door.get("seam", 1.1)
        body, seam = door.get("body", "#4d4d4d"), door.get("fill", "#3b3b3b")
        unit = squircle_path(r=1, c=0)

        def sq(hx, hy, dy=0.0, **attrs):
            return ET.SubElement(clip, f"{{{SVG}}}path", dict(
                {"d": unit, "transform": f"matrix({hx} 0 0 {hy} {cx} {cy + dy})"}, **attrs))

        ix, iy = hw - w, hh - w
        cpi = ET.SubElement(d, f"{{{SVG}}}clipPath", {"id": "doorin"})
        ET.SubElement(cpi, f"{{{SVG}}}path", {"d": unit, "transform": f"matrix({ix} 0 0 {iy} {cx} {cy})"})
        sq(hw, hh, w, fill="#ffffff", opacity="0.15")          # light edge below the door
        sq(hw, hh, fill=body)                                  # cover it, except the bottom sliver
        sq(ix, iy, fill="#ffffff", opacity="0.15")             # light edge inside, at the top
        inner = ET.SubElement(clip, f"{{{SVG}}}g", {"clip-path": "url(#doorin)"})
        ET.SubElement(inner, f"{{{SVG}}}path", {"d": unit, "fill": body,
                                                "transform": f"matrix({ix} 0 0 {iy} {cx} {cy + w})"})
        # the seam itself: a squircle outline of width w along the door edge
        ring = ET.SubElement(clip, f"{{{SVG}}}path", {"d": unit, "fill": "none", "stroke": seam,
                                                       "stroke-width": str(w / ((hw + hh) / 2)),
                                                       "vector-effect": "none"})
        ring.set("transform", f"matrix({hw - w / 2} 0 0 {hh - w / 2} {cx} {cy})")

    # details that keep their shape but follow the stretched background
    for e in places + corners:
        bb = render_bbox(defs, e, cfg["tile"])
        if not bb:
            continue
        if e in corners:   # pin to the top-right corner of the stretched tile
            ex, ey = bb[2], bb[1]
            nx, ny = sx * ex + tx, sy * ey + ty
        else:
            ex, ey = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            nx, ny = sx * ex + tx, sy * ey + ty
        pg = ET.SubElement(clip, f"{{{SVG}}}g", {"transform": f"matrix({s} 0 0 {s} {nx - s * ex} {ny - s * ey})"})
        pg.append(copy.deepcopy(e))
    # pictograms: exact Yaru proportions, drawn over (may overhang the plate like in Yaru)
    ug = ET.SubElement(out, f"{{{SVG}}}g", {"transform": f"matrix({s} 0 0 {s} {ux} {uy})"})
    # optional: some pictogram pieces drawn a little smaller, about their common centre
    shrink = cfg.get("shrink")
    if shrink:
        ids, k = shrink
        group = [e for e in uniform if e.attrib.get("id") in ids]
        boxes = [b for b in (render_bbox(defs, e, cfg["tile"]) for e in group) if b]
        if boxes:
            bx0 = min(b[0] for b in boxes); by0 = min(b[1] for b in boxes)
            bx1 = max(b[2] for b in boxes); by1 = max(b[3] for b in boxes)
            gcx, gcy = (bx0 + bx1) / 2, (by0 + by1) / 2
            sg = ET.SubElement(ug, f"{{{SVG}}}g", {"transform": f"matrix({k} 0 0 {k} {gcx * (1 - k)} {gcy * (1 - k)})"})
            for e in group:
                sg.append(copy.deepcopy(e))
            uniform = [e for e in uniform if e not in group]
    for e in uniform:
        ug.append(copy.deepcopy(e))
    path = OUT / f"{key}.svg"
    path.write_bytes(ET.tostring(out))
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--out"]:
        OUT = Path(args[1])
        args = args[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    keys = args or [k for k in ICONS if "@" not in k]
    for k in keys:
        print(compose(k, ICONS[k]))
