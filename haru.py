#!/usr/bin/env python3
"""haru: generate a personal icon theme that keeps Yaru but puts
every application icon on a uniform superellipse ("squircle") plate.

Subcommands
  generate   scan apps, render icons, write theme + launcher overrides
  sheet      (re)build the contact sheet only
  restore-launchers   undo every launcher change this tool made

Only application icons are produced. Everything else (symbolic, folder,
mime, status icons) is inherited untouched from the active Yaru variant.
"""

import argparse
import configparser
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import cairo
import gi
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Rsvg", "2.0")
from gi.repository import GdkPixbuf, Rsvg  # noqa: E402

HOME = Path.home()
THEME_NAME = "Haru"
THEME_DIR = HOME / ".local/share/icons" / THEME_NAME
DATA_DIR = HOME / ".local/share/haru"
STATE_DIR = HOME / ".local/state/haru"
USER_APPS = HOME / ".local/share/applications"
CONFIG_PATH = HOME / ".config/haru/config.toml"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.toml"
ART_DIR = Path(__file__).resolve().parent / "art"

MARK_OVERRIDE = "X-Haru-Override"        # copy we created
MARK_SOURCE = "X-Haru-Source"            # file it was copied from
MARK_ORIG_ICON = "X-Haru-Original-Icon"  # user file we edited in place
ICON_PREFIX = "haru-"

MASTER = 1024
SIZES = [(16, 1), (16, 2), (24, 1), (24, 2), (32, 1), (32, 2), (48, 1), (48, 2),
         (64, 1), (64, 2), (128, 1), (128, 2), (256, 1), (256, 2)]
RENDER_VERSION = "4"   # bump to force a full re-render

TERMINAL_NAMES = {"utilities-terminal", "org.gnome.Ptyxis", "org.gnome.Terminal",
                  "org.gnome.Console", "terminal-app", "gnome-terminal", "terminal",
                  "com.gexperts.Tilix", "xterm", "kitty", "Alacritty",
                  "org.wezfurlong.wezterm", "com.mitchellh.ghostty"}


# --------------------------------------------------------------- config ----

DEFAULTS = {
    "theme": {"base": "auto"},
    "shape": {"plate": 0.875, "exponent": 5.0, "filled_scale": 1.05, "filled_edge": 0.05, "logo_size": 0.72,
              "rim_width": 1.0, "rim_top_alpha": 0.34, "rim_bottom_alpha": 0.05,
              "shadow_opacity": 0.28},
    "colors": {"plate_top": "#FCF9F2", "plate_bottom": "#EEE8DC",
               "terminal_top": "#6A305A", "terminal_bottom": "#3A1A38"},
    "overrides": {},
    "skip": [],
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    for path in (DEFAULT_CONFIG, CONFIG_PATH):
        if path.exists():
            with open(path, "rb") as f:
                user = tomllib.load(f)
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    return cfg


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------ desktop -------

def data_dirs():
    env = os.environ.get("XDG_DATA_DIRS", "")
    dirs = [HOME / ".local/share"]
    defaults = ["/usr/share/ubuntu", "/usr/share/gnome",
                str(HOME / ".local/share/flatpak/exports/share"),
                "/var/lib/flatpak/exports/share", "/usr/local/share", "/usr/share",
                "/var/lib/snapd/desktop"]
    for d in env.split(":") + defaults:
        if d and Path(d) not in dirs:
            dirs.append(Path(d))
    return dirs


def read_desktop(path):
    cp = configparser.RawConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
        return dict(cp["Desktop Entry"])
    except Exception:
        return None


def is_visible(e):
    if e.get("Type") != "Application":
        return False
    if e.get("NoDisplay", "").lower() == "true" or e.get("Hidden", "").lower() == "true":
        return False
    desk = {"GNOME", "ubuntu"}
    only = {x for x in e.get("OnlyShowIn", "").split(";") if x}
    nots = {x for x in e.get("NotShowIn", "").split(";") if x}
    if only and not (only & desk):
        return False
    if nots & desk:
        return False
    return True


def scan_apps():
    """Return {desktop_id: app} where app describes the *original* launcher."""
    found, ours = {}, {}
    for d in data_dirs():
        adir = d / "applications"
        if not adir.is_dir():
            continue
        for p in sorted(adir.rglob("*.desktop")):
            did = str(p.relative_to(adir)).replace("/", "-")
            e = read_desktop(p)
            if e is None:
                continue
            if e.get(MARK_OVERRIDE) == "true":
                ours[did] = p          # our own copy: keep looking for the original
                continue
            if did in found:
                continue
            icon = e.get(MARK_ORIG_ICON) or e.get("Icon", "")
            found[did] = {"id": did, "path": p, "entry": e, "icon": icon.strip(),
                          "name": e.get("Name", did), "visible": is_visible(e),
                          "user_file": adir == USER_APPS,
                          "terminal": "TerminalEmulator" in e.get("Categories", "")}
    return found, ours


# ----------------------------------------------------------- icon lookup ----

class IconLookup:
    def __init__(self, base):
        self.bases = [HOME / ".local/share/icons", HOME / ".icons"] + \
                     [d / "icons" for d in data_dirs()[1:]]
        self.chain = self._chain(base)
        self.yaru_chain = [t for t in self.chain if t.lower().startswith("yaru")]
        self._dirs = {}

    def _index(self, theme):
        for b in self.bases:
            p = b / theme / "index.theme"
            if p.exists():
                cp = configparser.RawConfigParser(strict=False, interpolation=None)
                cp.optionxform = str
                cp.read(p, encoding="utf-8")
                return cp
        return None

    def _chain(self, base):
        out, queue = [], [base]
        while queue:
            t = queue.pop(0)
            if t in out or t == THEME_NAME:
                continue
            out.append(t)
            idx = self._index(t)
            if idx and idx.has_option("Icon Theme", "Inherits"):
                queue += [x.strip() for x in idx.get("Icon Theme", "Inherits").split(",") if x.strip()]
        if "hicolor" in out:
            out.remove("hicolor")
        out.append("hicolor")
        return out

    def _theme_dirs(self, theme):
        if theme in self._dirs:
            return self._dirs[theme]
        res = []
        idx = self._index(theme)
        if idx:
            sec = idx["Icon Theme"]
            names = [x.strip() for x in (sec.get("Directories", "") + "," +
                                         sec.get("ScaledDirectories", "")).split(",") if x.strip()]
            for n in dict.fromkeys(names):
                if not idx.has_section(n):
                    continue
                s = idx[n]
                size = int(s.get("Size", "0"))
                scale = int(s.get("Scale", "1"))
                typ = s.get("Type", "Threshold")
                maxs = int(s.get("MaxSize", str(size)))
                eff = 4096 if (typ == "Scalable" and maxs >= 128) else max(size, maxs if typ == "Scalable" else size) * scale
                for b in self.bases:
                    if (b / theme / n).is_dir():
                        res.append((b / theme / n, eff))
        self._dirs[theme] = res
        return res

    def find_in(self, themes, name):
        for theme in themes:
            best = None
            for d, eff in self._theme_dirs(theme):
                for ext in (".svg", ".png", ".xpm"):
                    p = d / (name + ext)
                    if p.exists():
                        score = eff + (1 if ext == ".svg" else 0)
                        if best is None or score > best[0]:
                            best = (score, p)
            if best:
                return best[1], theme
        return None, None

    def resolve(self, name):
        if name.endswith((".png", ".svg", ".xpm")):
            name = name.rsplit(".", 1)[0]
        p, theme = self.find_in(self.chain, name)
        if p:
            return p, theme
        for ext in (".svg", ".png", ".xpm"):
            p = Path("/usr/share/pixmaps") / (name + ext)
            if p.exists():
                return p, "pixmaps"
        return None, None


def active_base_theme(cfg):
    if cfg["theme"].get("base", "auto") != "auto":
        return cfg["theme"]["base"]
    saved = STATE_DIR / "base-theme"
    cur = icon_theme()
    # the theme is built on Yaru: follow the Yaru variant in use (accent, dark),
    # and fall back to plain Yaru when another icon theme was active
    if cur and cur != THEME_NAME and cur.startswith("Yaru"):
        return cur
    if saved.exists() and saved.read_text().strip().startswith("Yaru"):
        return saved.read_text().strip()
    return "Yaru"


# --------------------------------------------------------------- loading ----

def pil_from_cairo(surface):
    surface.flush()
    w, h = surface.get_width(), surface.get_height()
    return Image.frombuffer("RGBA", (w, h), bytes(surface.get_data()), "raw", "BGRa",
                            surface.get_stride(), 1).copy()


def is_svg(path):
    try:
        with open(path, "rb") as f:
            head = f.read(512)
    except OSError:
        return False
    if head[:2] == b"\x1f\x8b":
        return True
    return b"<svg" in head or (b"<?xml" in head and not head.startswith(b"\x89PNG"))


def svg_size(path):
    h = Rsvg.Handle.new_from_file(str(path))
    ok, w, hh = h.get_intrinsic_size_in_pixels()
    if not ok or not w or not hh:
        return 1.0
    return w / hh


def render_svg(path, w, h):
    """Render an SVG with librsvg (the engine behind rsvg-convert)."""
    exe = shutil.which("rsvg-convert")
    if exe:
        out = subprocess.run([exe, "-w", str(w), "-h", str(h), "--keep-aspect-ratio", str(path)],
                             capture_output=True, check=True).stdout
        im = Image.open(io.BytesIO(out)).convert("RGBA")
        if im.size != (w, h):
            canvas = Image.new("RGBA", (w, h))
            canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
            im = canvas
        return im
    # Same librsvg engine, through GdkPixbuf's SVG loader (no python3-gi-cairo needed).
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), w, h, True)
    im = pixbuf_to_pil(pb)
    if im.size != (w, h):
        canvas = Image.new("RGBA", (w, h))
        canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        im = canvas
    return im


def load_raster(path):
    return pixbuf_to_pil(GdkPixbuf.Pixbuf.new_from_file(str(path)))


def pixbuf_to_pil(pb):
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    return Image.frombuffer("RGBA", (pb.get_width(), pb.get_height()), pb.get_pixels(),
                            "raw", "RGBA", pb.get_rowstride(), 1).copy()


class Source:
    """An icon source that can be rendered at arbitrary size."""

    def __init__(self, path):
        self.path = Path(path)
        self.svg = is_svg(self.path)
        if self.svg:
            ar = svg_size(self.path)
            self.w, self.h = (MASTER, round(MASTER / ar)) if ar >= 1 else (round(MASTER * ar), MASTER)
            self.native = None
            self.img = render_svg(self.path, self.w, self.h)
        else:
            self.img = load_raster(self.path)
            self.w, self.h = self.img.size
            self.native = max(self.w, self.h)

    def at_scale(self, k):
        """Return the full source image scaled by k (relative to self.img)."""
        w, h = max(1, round(self.w * k)), max(1, round(self.h * k))
        if self.svg:
            return render_svg(self.path, w, h)
        return self.img.resize((w, h), Image.LANCZOS)


# -------------------------------------------------------------- analysis ----

def mask_bbox(alpha, thr):
    return alpha.point(lambda a: 255 if a > thr else 0).getbbox()


def analyse(img):
    a = img.getchannel("A")
    any_bb = mask_bbox(a, 8)
    if not any_bb:
        return None
    body_bb = mask_bbox(a, 64) or any_bb
    solid = a.point(lambda v: 255 if v > 200 else 0)
    sbb = solid.getbbox() or body_bb
    sw, sh = sbb[2] - sbb[0], sbb[3] - sbb[1]
    fill = solid.crop(sbb).histogram()[255] / max(1, sw * sh)
    aspect = sw / max(1, sh)
    # how far the visible body sticks out of the solid square (badges, shadows)
    side = max(sw, sh)
    overhang = max(sbb[0] - body_bb[0], sbb[1] - body_bb[1],
                   body_bb[2] - sbb[2], body_bb[3] - sbb[3]) / max(1, side)
    # colour variance along the square's edge: a filled tile has a uniform rim
    inset = max(2, int(side * 0.04))
    strips = [(sbb[0] + side // 4, sbb[1] + inset, sbb[2] - side // 4, sbb[1] + inset * 2),
              (sbb[0] + side // 4, sbb[3] - inset * 2, sbb[2] - side // 4, sbb[3] - inset),
              (sbb[0] + inset, sbb[1] + side // 4, sbb[0] + inset * 2, sbb[3] - side // 4),
              (sbb[2] - inset * 2, sbb[1] + side // 4, sbb[2] - inset, sbb[3] - side // 4)]
    cols = []
    for s in strips:
        if s[2] > s[0] and s[3] > s[1]:
            cols.append(ImageStat.Stat(img.crop(s).convert("RGB")).mean)
    edge = tuple(int(sum(c[i] for c in cols) / len(cols)) for i in range(3)) if cols else (255, 255, 255)
    is_square = 0.93 <= aspect <= 1.075 and fill >= 0.90 and overhang <= 0.06
    return {"any": any_bb, "body": body_bb, "solid": sbb, "fill": round(fill, 3),
            "aspect": round(aspect, 3), "overhang": round(overhang, 3), "edge": edge,
            "square": is_square,
            "squarish": 0.85 <= aspect <= 1.18 and 0.72 <= fill < 0.90}


# -------------------------------------------------------------- drawing ----

def squircle_path(cr, cx, cy, r, n, steps=720):
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = cx + r * math.copysign(abs(c) ** (2 / n), c)
        y = cy + r * math.copysign(abs(s) ** (2 / n), s)
        (cr.move_to if i == 0 else cr.line_to)(x, y)
    cr.close_path()


def squircle_mask(size, plate, n):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    cr.set_antialias(cairo.ANTIALIAS_BEST)
    squircle_path(cr, size / 2, size / 2, plate / 2, n)
    cr.set_source_rgba(1, 1, 1, 1)
    cr.fill()
    return pil_from_cairo(surf).getchannel("A")


def rim_layer(size, plate, n, width, top_a, bottom_a):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    cr.set_antialias(cairo.ANTIALIAS_BEST)
    squircle_path(cr, size / 2, size / 2, plate / 2 - width / 2, n)
    y0 = (size - plate) / 2
    g = cairo.LinearGradient(0, y0, 0, y0 + plate)
    g.add_color_stop_rgba(0, 1, 1, 1, top_a)
    g.add_color_stop_rgba(1, 1, 1, 1, bottom_a)
    cr.set_source(g)
    cr.set_line_width(width)
    cr.stroke()
    return pil_from_cairo(surf)


def vgradient(size, top, bottom):
    col = Image.new("RGBA", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        col.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    # BILINEAR, not NEAREST: python3-pil 12.3.0-1ubuntu2 (Nov 2026) breaks NEAREST resizes
    return col.resize((size, size), Image.BILINEAR)


def terminal_glyph(size, plate):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    o = (size - plate) / 2
    P = plate
    cr.set_source_rgba(1, 1, 1, 1)
    cr.set_line_width(P * 0.065)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(o + P * 0.21, o + P * 0.22)
    cr.line_to(o + P * 0.34, o + P * 0.315)
    cr.line_to(o + P * 0.21, o + P * 0.41)
    cr.stroke()
    cr.move_to(o + P * 0.40, o + P * 0.41)
    cr.line_to(o + P * 0.56, o + P * 0.41)
    cr.stroke()
    return pil_from_cairo(surf)


def extend_edges(img, box):
    """Keep img inside box and repeat box's outermost pixels outward over the rest.

    Used for "filled" icons: the source tile's own rim, bottom shading and rounded
    corners sit in that outer band, and would otherwise show just inside the squircle.
    Nothing is scaled; the art inside the box stays exactly where and how it was."""
    x0, y0, x1, y1 = box
    w, h = img.size
    if not (0 < x0 < x1 < w and 0 < y0 < y1 < h):
        return img
    out = Image.new("RGBA", (w, h))
    out.paste(img.crop(box), (x0, y0))
    iw, ih = x1 - x0, y1 - y0

    def strip(b, size):  # BILINEAR: NEAREST resizes are broken in python3-pil 12.3.0-1ubuntu2
        return img.crop(b).resize(size, Image.BILINEAR)

    out.paste(strip((x0, y0, x1, y0 + 1), (iw, y0)), (x0, 0))
    out.paste(strip((x0, y1 - 1, x1, y1), (iw, h - y1)), (x0, y1))
    out.paste(strip((x0, y0, x0 + 1, y1), (x0, ih)), (0, y0))
    out.paste(strip((x1 - 1, y0, x1, y1), (w - x1, ih)), (x1, y0))
    for px, py, bx, by, bw, bh in ((x0, y0, 0, 0, x0, y0), (x1 - 1, y0, x1, 0, w - x1, y0),
                                   (x0, y1 - 1, 0, y1, x0, h - y1), (x1 - 1, y1 - 1, x1, y1, w - x1, h - y1)):
        out.paste(Image.new("RGBA", (bw, bh), img.getpixel((px, py))), (bx, by))
    return out


def render_master(src, info, style, cfg, opts):
    """Return the un-rimmed master image (MASTER x MASTER) for one icon."""
    sh = cfg["shape"]
    co = cfg["colors"]
    plate = MASTER * float(opts.get("plate", sh["plate"]))
    off = (MASTER - plate) / 2
    canvas = Image.new("RGBA", (MASTER, MASTER))

    if style == "art":
        # finished squircle artwork (art/<icon>.svg): already laid out on the 87.5 % plate
        canvas.alpha_composite(src.at_scale(MASTER / max(src.w, src.h)))
        return canvas

    if style == "terminal":
        canvas.alpha_composite(vgradient(MASTER, hex_rgb(co["terminal_top"]), hex_rgb(co["terminal_bottom"])))
        canvas.alpha_composite(terminal_glyph(MASTER, plate))
        return canvas

    if style == "filled":
        sbb = info["solid"]
        side = max(sbb[2] - sbb[0], sbb[3] - sbb[1])
        k = plate * float(opts.get("filled_scale", sh["filled_scale"])) / side
        img = src.at_scale(k)
        edge = float(opts.get("filled_edge", sh.get("filled_edge", 0)))
        if edge > 0:
            d = side * edge
            img = extend_edges(img, tuple(round(v * k) for v in (sbb[0] + d, sbb[1] + d, sbb[2] - d, sbb[3] - d)))
        cx, cy = (sbb[0] + sbb[2]) / 2 * k, (sbb[1] + sbb[3]) / 2 * k
        bg = tuple(opts["background"]) if "background" in opts else info["edge"]
        if isinstance(bg, str):
            bg = hex_rgb(bg)
        canvas.paste(Image.new("RGBA", (MASTER, MASTER), tuple(bg[:3]) + (255,)))
        canvas.alpha_composite(img, (round(MASTER / 2 - cx), round(MASTER / 2 - cy)))
        return canvas

    # free-form logo
    if "plate_checker" in opts:
        # a board pattern (e.g. Chess on a wooden board): two colours, n x n squares, lit from the top
        ca, cb = (hex_rgb(c) for c in opts["plate_checker"])
        n = int(opts.get("checker_size", 4))
        board = Image.new("RGBA", (MASTER, MASTER), ca + (255,))
        bd = ImageDraw.Draw(board)
        cell = MASTER / n
        for i in range(n):
            for j in range(n):
                if (i + j) % 2:
                    bd.rectangle((i * cell, j * cell, (i + 1) * cell, (j + 1) * cell), fill=cb + (255,))
        canvas.alpha_composite(Image.blend(board, vgradient(MASTER, (255, 255, 255), (0, 0, 0)), 0.10))
    else:
        canvas.alpha_composite(vgradient(MASTER, hex_rgb(opts.get("plate_top", co["plate_top"])),
                                         hex_rgb(opts.get("plate_bottom", co["plate_bottom"]))))
    bb = info["body"]
    longest = max(bb[2] - bb[0], bb[3] - bb[1])
    k = plate * float(opts.get("logo_size", sh["logo_size"])) / longest
    img = src.at_scale(k)
    cx, cy = (bb[0] + bb[2]) / 2 * k, (bb[1] + bb[3]) / 2 * k
    pos = (round(MASTER / 2 - cx), round(MASTER / 2 - cy))
    layer = Image.new("RGBA", (MASTER, MASTER))
    layer.alpha_composite(img, pos) if pos[0] >= 0 and pos[1] >= 0 else layer.paste(img, pos, img)
    a = layer.getchannel("A")
    op = float(opts.get("shadow_opacity", sh["shadow_opacity"]))
    for blur, dy, strength in ((plate * 0.035, plate * 0.025, 0.55), (plate * 0.008, plate * 0.008, 0.45)):
        sa = a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: round(v * op * strength))
        shadow = Image.new("RGBA", (MASTER, MASTER), (60, 45, 25, 0))
        shadow.putalpha(sa)
        canvas.alpha_composite(shadow, (0, round(dy)))
    canvas.alpha_composite(layer)
    return canvas


def finish(master, size, cfg, opts):
    sh = cfg["shape"]
    n = float(sh["exponent"])
    plate_frac = float(opts.get("plate", sh["plate"]))
    img = master.resize((size, size), Image.LANCZOS)
    plate = size * plate_frac
    mask = squircle_mask(size, plate, n)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    width = max(float(sh["rim_width"]), size / 128 * float(sh["rim_width"]))
    img.alpha_composite(rim_layer(size, plate, n, width, float(opts.get("rim_top_alpha", sh["rim_top_alpha"])),
                                  float(opts.get("rim_bottom_alpha", sh["rim_bottom_alpha"]))))
    return img


# ------------------------------------------------------------- pipeline ----

def png_bytes(img):
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()


def write_if_changed(path, data):
    path = Path(path)
    if isinstance(data, str):
        data = data.encode()
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


def size_dir(size, scale):
    return f"{size}x{size}" + ("@2x" if scale == 2 else "") + "/apps"


def write_index(base):
    lines = ["[Icon Theme]", f"Name={THEME_NAME}",
             "Comment=Yaru with every application icon on a squircle (generated by haru)",
             f"Inherits={base},hicolor", "Example=org.gnome.Nautilus",
             "Directories=" + ",".join(size_dir(s, k) for s, k in SIZES), ""]
    for s, k in SIZES:
        lines += [f"[{size_dir(s, k)}]", "Context=Applications", f"Size={s}"]
        if k == 2:
            lines.append("Scale=2")
        if s == 256:
            lines += ["Type=Scalable", "MinSize=128", "MaxSize=512"]
        else:
            lines += ["Type=Fixed"]
        lines.append("")
    write_if_changed(THEME_DIR / "index.theme", "\n".join(lines))


def pick_style(app, info, opts, cfg):
    if "style" in opts:
        return opts["style"]
    if app["terminal"] or app["icon"] in TERMINAL_NAMES:
        return "terminal"
    if info and info["square"]:
        return "filled"
    return "logo"


def override_opts(cfg, app, icon_name):
    ov = cfg.get("overrides", {})
    opts = {}
    for key in (icon_name, app["icon"], app["id"], app["id"].removesuffix(".desktop")):
        v = ov.get(key)
        if isinstance(v, str):
            opts.setdefault("style", v)
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                opts.setdefault(k2, v2)
    return opts


GENERIC_ICON_STEMS = {"icon", "logo", "app", "application", "launcher", "snap"}


def snap_aliases(app):
    did = app["id"].removesuffix(".desktop")
    names = []
    # the file name of the launcher's own icon is the best hint
    # (snap-store ships "app-center.png"; Yaru's "snap-store" is the old Snap Store art)
    stem = Path(app["icon"]).name.rsplit(".", 1)[0]
    if len(stem) > 3 and stem.lower() not in GENERIC_ICON_STEMS and not stem.lower().startswith("default"):
        names.append(stem)
    if "_" in did:
        snap, rest = did.split("_", 1)
        names += [rest, snap]
    else:
        names.append(did)
    wm = app["entry"].get("StartupWMClass")
    if wm:
        names.append(wm.lower())
    return list(dict.fromkeys(names))


def generate(args):
    cfg = load_config()
    base = active_base_theme(cfg)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "base-theme").write_text(base + "\n")
    lookup = IconLookup(base)
    apps, ours = scan_apps()
    skip = set(cfg.get("skip", []))
    manifest_path = DATA_DIR / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() and not args.force else {}
    cfg_hash = hashlib.sha1((RENDER_VERSION + json.dumps(cfg, sort_keys=True)).encode()).hexdigest()[:12]

    report = {"base": base, "apps": [], "missing": [], "launchers": []}
    jobs = {}   # icon_name -> job
    for did, app in sorted(apps.items()):
        if not app["visible"] or did in skip or did.removesuffix(".desktop") in skip:
            continue
        icon = app["icon"]
        src, origin, icon_name, needs_launcher = None, None, None, False
        forced = override_opts(cfg, app, icon).get("icon")
        if forced:
            src, origin = Path(os.path.expanduser(forced)), "override"
        if not icon and not src:
            report["missing"].append({"id": did, "name": app["name"], "why": "no Icon= line"})
            continue
        if icon.startswith("/"):
            needs_launcher = True
            icon_name = ICON_PREFIX + did.removesuffix(".desktop")
            if not src:
                for alias in snap_aliases(app):
                    p, theme = lookup.find_in(lookup.yaru_chain, alias)
                    if p:
                        src, origin = p, f"{theme} ({alias})"
                        break
            if not src and Path(icon).exists():
                src, origin = Path(icon), "launcher path"
        else:
            icon_name = icon.rsplit(".", 1)[0] if icon.endswith((".png", ".svg", ".xpm")) else icon
            if icon_name in skip:
                continue
            if not src:
                src, origin = lookup.resolve(icon_name)
        if not src or not Path(src).exists():
            report["missing"].append({"id": did, "name": app["name"], "why": f"icon '{icon}' not found"})
            continue
        if needs_launcher:
            report["launchers"].append(did)
        job = jobs.setdefault(icon_name, {"name": icon_name, "src": str(Path(src).resolve()),
                                          "origin": origin, "apps": [], "opts": {}, "terminal": False})
        job["apps"].append({"id": did, "name": app["name"], "launcher": needs_launcher})
        job["opts"].update(override_opts(cfg, app, icon_name))
        job["terminal"] |= app["terminal"] or icon_name in TERMINAL_NAMES
        job["app"] = app

    write_index(base)
    manifest = {}
    rendered = 0
    for name, job in sorted(jobs.items()):
        try:
            if job["opts"].get("style") == "art":
                art = Path(os.path.expanduser(str(job["opts"].get("art", f"{name}.svg"))))
                if not art.is_absolute():
                    art = ART_DIR / art          # plain file names live in the theme's art/ folder
                if not art.exists():
                    raise FileNotFoundError(f"artwork {art} is missing")
                job.setdefault("orig_src", job["src"])
                job["src"] = str(art)
            st = os.stat(job["src"])
            key = f"{cfg_hash}:{job['src']}:{st.st_mtime_ns}:{st.st_size}:{json.dumps(job['opts'], sort_keys=True)}:{job['terminal']}"
            prev = old.get(name)
            if prev and prev.get("key") == key and all((THEME_DIR / size_dir(s, k) / f"{name}.png").exists() for s, k in SIZES):
                manifest[name] = prev
                continue
            source = Source(job["src"])
            info = analyse(source.img)
            if info is None:
                report["missing"].append({"id": job["apps"][0]["id"], "name": job["apps"][0]["name"],
                                          "why": "icon image is empty"})
                continue
            app = dict(job["app"], terminal=job["terminal"])
            style = pick_style(app, info, job["opts"], cfg)
            master = render_master(source, info, style, cfg, job["opts"])
            for s, k in SIZES:
                write_if_changed(THEME_DIR / size_dir(s, k) / f"{name}.png", png_bytes(finish(master, s * k, cfg, job["opts"])))
            native = source.native
            manifest[name] = {"key": key, "style": style, "src": job["src"], "origin": job["origin"],
                              "apps": job["apps"], "native": native,
                              "lowres": bool(native and native < 128 and style != "terminal"),
                              "metrics": {k2: info[k2] for k2 in ("fill", "aspect", "overhang", "square", "squarish")}}
            rendered += 1
        except Exception as ex:  # keep going, report the failure
            report["missing"].append({"id": job["apps"][0]["id"], "name": job["apps"][0]["name"],
                                      "why": f"could not render {job['src']}: {ex}"})
    # remove icons for apps that are gone
    for name in set(old) - set(manifest):
        for s, k in SIZES:
            p = THEME_DIR / size_dir(s, k) / f"{name}.png"
            if p.exists():
                p.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_if_changed(manifest_path, json.dumps(manifest, indent=1, sort_keys=True))

    changed_launchers = 0
    if (STATE_DIR / "installed").exists():
        changed_launchers = sync_launchers(apps, ours, {a["id"] for j in jobs.values() for a in j["apps"] if a["launcher"]},
                                           {a["id"]: n for n, j in jobs.items() for a in j["apps"]})
        write_fallbacks(jobs)
    os.utime(THEME_DIR)
    if changed_launchers and not args.no_refresh:
        refresh_shell()

    report["apps"] = [{"icon": n, **{k: v for k, v in m.items() if k != "key"}} for n, m in sorted(manifest.items())]
    write_if_changed(DATA_DIR / "report.json", json.dumps(report, indent=1))
    write_report_txt(report)
    if rendered or args.sheet or not (DATA_DIR / "contact-sheet.png").exists():
        contact_sheet(manifest, report)
    print(f"{THEME_NAME}: {len(manifest)} icons ({rendered} rendered), base {base}, "
          f"{len(report['launchers'])} launcher overrides ({changed_launchers} changed), "
          f"{len(report['missing'])} without usable icon")
    for m in report["missing"]:
        print(f"  no icon: {m['name']} [{m['id']}]: {m['why']}")


# ------------------------------------------------------------- launchers ----

def set_key(text, key, value):
    """Set key=value inside [Desktop Entry] of a .desktop file's text."""
    out, in_main, done = [], False, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            if in_main and not done:
                out.append(f"{key}={value}")
                done = True
            in_main = s == "[Desktop Entry]"
        elif in_main and s.split("=", 1)[0].strip() == key:
            if not done:
                out.append(f"{key}={value}")
                done = True
            continue
        out.append(line)
    if in_main and not done:
        out.append(f"{key}={value}")
    return "\n".join(out) + "\n"


def del_key(text, key):
    out, in_main = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_main = s == "[Desktop Entry]"
        elif in_main and s.split("=", 1)[0].strip() == key:
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def sync_launchers(apps, ours, wanted, icon_of):
    changed = 0
    USER_APPS.mkdir(parents=True, exist_ok=True)
    for did in wanted:
        app = apps[did]
        name = icon_of[did]
        if app["user_file"]:
            text = app["path"].read_text(encoding="utf-8")
            new = set_key(set_key(text, MARK_ORIG_ICON, app["icon"]), "Icon", name)
            changed += write_if_changed(app["path"], new)
        else:
            text = app["path"].read_text(encoding="utf-8")
            new = set_key(set_key(set_key(text, "Icon", name), MARK_OVERRIDE, "true"), MARK_SOURCE, str(app["path"]))
            changed += write_if_changed(USER_APPS / did, new)
    # remove our copies whose original is gone or no longer needs one
    for did, p in ours.items():
        if did not in wanted:
            p.unlink(missing_ok=True)
            changed += 1
    return changed


HICOLOR = HOME / ".local/share/icons/hicolor"


def write_fallbacks(jobs):
    """Plain (un-squircled) copies of the icons that launchers now refer to by a
    new name, in hicolor, so those apps keep a proper icon under ANY icon theme
    (for instance after picking another accent colour in Settings)."""
    keep = set()
    for name, job in jobs.items():
        if not name.startswith(ICON_PREFIX):
            continue
        src = Path(job.get("orig_src", job["src"]))   # the app's own icon, not our artwork
        if is_svg(src):
            dst = HICOLOR / "scalable/apps" / f"{name}.svg"
            write_if_changed(dst, src.read_bytes())
        else:
            im = load_raster(src)
            im.thumbnail((256, 256), Image.LANCZOS)
            dst = HICOLOR / "256x256/apps" / f"{name}.png"
            write_if_changed(dst, png_bytes(im))
        keep.add(dst)
    for sub in ("scalable/apps", "256x256/apps"):
        for p in (HICOLOR / sub).glob(ICON_PREFIX + "*"):
            if p not in keep:
                p.unlink()
    touch_hicolor()


def remove_fallbacks():
    for sub in ("scalable/apps", "256x256/apps"):
        for p in (HICOLOR / sub).glob(ICON_PREFIX + "*"):
            p.unlink()
    touch_hicolor()


def touch_hicolor():
    # icon themes only notice new files when the theme folder itself changes
    if HICOLOR.is_dir():
        os.utime(HICOLOR)


def icon_theme():
    return subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"],
                          capture_output=True, text=True).stdout.strip().strip("'")


def refresh_shell():
    """Make GNOME Shell pick up launchers whose Icon= just changed.

    The Shell builds each app-grid icon from the launcher it had loaded at the
    time and does not rebuild it when only the launcher changes, so a launcher
    that now points to a new icon name can be left showing the generic gear.
    Switching the icon theme away and back makes it rebuild every icon. We wait
    first so the Shell has read the new launchers, and step away to hicolor
    (not a Yaru variant) so the accent watcher leaves it alone."""
    if icon_theme() != THEME_NAME:
        return
    import time
    time.sleep(3)
    subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "hicolor"])
    time.sleep(1)
    subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", THEME_NAME])


def restore_launchers(args=None):
    remove_fallbacks()
    n = 0
    if USER_APPS.is_dir():
        for p in USER_APPS.glob("*.desktop"):
            e = read_desktop(p)
            if not e:
                continue
            if e.get(MARK_OVERRIDE) == "true":
                p.unlink()
                n += 1
            elif MARK_ORIG_ICON in e:
                text = p.read_text(encoding="utf-8")
                text = del_key(set_key(text, "Icon", e[MARK_ORIG_ICON]), MARK_ORIG_ICON)
                p.write_text(text, encoding="utf-8")
                n += 1
    print(f"restored {n} launchers")


# ---------------------------------------------------------------- report ----

def write_report_txt(report):
    lines = [f"Haru report (base theme {report['base']})", ""]
    by = {}
    for a in report["apps"]:
        by.setdefault(a["style"], []).append(a)
    for style in ("filled", "logo", "art", "terminal"):
        lines.append(f"== {style} ({len(by.get(style, []))})")
        for a in by.get(style, []):
            names = ", ".join(x["name"] for x in a["apps"])
            flag = "  [low-res source]" if a.get("lowres") else ""
            lines.append(f"  {a['icon']:<45} {names}  <- {a['origin']}{flag}")
        lines.append("")
    lines.append(f"== launchers given a themed icon name ({len(report['launchers'])})")
    lines += [f"  {x}" for x in report["launchers"]]
    lines.append("")
    lines.append(f"== no usable icon ({len(report['missing'])})")
    lines += [f"  {m['name']} [{m['id']}]: {m['why']}" for m in report["missing"]]
    write_if_changed(DATA_DIR / "report.txt", "\n".join(lines) + "\n")


def font(size, bold=False):
    for f in ("/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf",
              "/usr/share/fonts/truetype/ubuntu/Ubuntu[wdth,wght].ttf"):
        if os.path.exists(f):
            ft = ImageFont.truetype(f, size)
            try:
                ft.set_variation_by_axes([100, 700 if bold else 400])
            except Exception:
                pass
            return ft
    return ImageFont.load_default()


def ellipsize(draw, text, ft, width):
    if draw.textlength(text, font=ft) <= width:
        return text
    while text and draw.textlength(text + "…", font=ft) > width:
        text = text[:-1]
    return text + "…"


def contact_sheet(manifest, report, out=None):
    """Two panels (dark and light desktop) of every generated icon."""
    items = []
    for name, m in sorted(manifest.items(), key=lambda kv: kv[1]["apps"][0]["name"].lower()):
        items.append((name, m))
    cols, cell_w, cell_h, icon = 8, 150, 150, 96
    rows = math.ceil(len(items) / cols)
    pad, head = 24, 70
    W = cols * cell_w + pad * 2
    panel_h = rows * cell_h + head
    miss_h = 40 + 22 * len(report["missing"]) if report["missing"] else 0
    H = panel_h * 2 + pad * 3 + miss_h
    sheet = Image.new("RGBA", (W, H), (36, 36, 36, 255))
    d = ImageDraw.Draw(sheet)
    f_title, f_name, f_tag = font(26, True), font(13), font(11, True)
    tagcol = {"filled": (120, 180, 255), "logo": (230, 190, 110), "art": (130, 210, 150), "terminal": (200, 120, 190)}
    for pi, (bg, fg, label) in enumerate((((48, 48, 48), (235, 235, 235), "Dark desktop"),
                                          ((246, 245, 244), (40, 40, 40), "Light desktop"))):
        y0 = pad + pi * (panel_h + pad)
        d.rounded_rectangle((pad // 2, y0, W - pad // 2, y0 + panel_h), 18, fill=bg)
        d.text((pad + 8, y0 + 18), f"{label}  ·  {len(items)} icons  ·  base {report['base']}",
               font=f_title, fill=fg)
        for i, (name, m) in enumerate(items):
            r, c = divmod(i, cols)
            x = pad + c * cell_w
            y = y0 + head + r * cell_h
            p = THEME_DIR / size_dir(48, 2) / f"{name}.png"
            if p.exists():
                im = Image.open(p).convert("RGBA").resize((icon, icon), Image.LANCZOS)
                sheet.alpha_composite(im, (x + (cell_w - icon) // 2, y + 4))
            label_txt = ellipsize(d, m["apps"][0]["name"], f_name, cell_w - 10)
            tw = d.textlength(label_txt, font=f_name)
            d.text((x + (cell_w - tw) / 2, y + icon + 10), label_txt, font=f_name, fill=fg)
            tag = m["style"] + (" · low-res" if m.get("lowres") else "")
            tw = d.textlength(tag, font=f_tag)
            d.text((x + (cell_w - tw) / 2, y + icon + 28), tag, font=f_tag, fill=tagcol.get(m["style"], fg))
    if report["missing"]:
        y = pad * 3 + panel_h * 2
        d.text((pad, y), "No usable icon:", font=font(18, True), fill=(255, 140, 120))
        for i, mm in enumerate(report["missing"]):
            d.text((pad, y + 28 + i * 22), f"{mm['name']}  [{mm['id']}]  {mm['why']}", font=f_name, fill=(230, 230, 230))
    out = Path(out or DATA_DIR / "contact-sheet.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(out, optimize=True)
    return out


def cmd_sheet(args):
    manifest = json.loads((DATA_DIR / "manifest.json").read_text())
    report = json.loads((DATA_DIR / "report.json").read_text())
    print(contact_sheet(manifest, report, args.out))


def main():
    ap = argparse.ArgumentParser(prog="haru")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--force", action="store_true", help="re-render every icon")
    g.add_argument("--sheet", action="store_true", help="always rebuild the contact sheet")
    g.add_argument("--no-refresh", action="store_true",
                   help="do not make GNOME Shell reload icons after launcher changes")
    g.set_defaults(func=generate)
    s = sub.add_parser("sheet")
    s.add_argument("--out")
    s.set_defaults(func=cmd_sheet)
    r = sub.add_parser("restore-launchers")
    r.set_defaults(func=restore_launchers)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
