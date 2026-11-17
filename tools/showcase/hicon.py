"""Render any Haru icon from the repo's config + art + Yaru (works for apps not installed)."""
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("haru", Path(__file__).resolve().parents[2] / "haru.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
cfg = h.load_config()
look = h.IconLookup("Yaru-blue")
ART = Path(__file__).resolve().parents[2] / "art"

def opts_for(key):
    o = cfg["overrides"].get(key, {})
    return {"style": o} if isinstance(o, str) else dict(o)

def haru(key, size=256, yaru_name=None):
    opts = opts_for(key)
    style = opts.get("style")
    if style == "art":
        a = Path(os.path.expanduser(str(opts.get("art", f"{key}.svg"))))
        src = a if a.is_absolute() else ART / a
    else:
        src, _ = look.resolve(yaru_name or key)
    s = h.Source(src); info = h.analyse(s.img)
    if not style:
        style = h.pick_style({"terminal": False, "icon": key}, info, opts, cfg)
    return h.finish(h.render_master(s, info, style, cfg, opts), size, cfg, opts)

def yaru(name, size=256):
    src, _ = look.resolve(name)
    s = h.Source(src)
    return s.at_scale(size / max(s.w, s.h))
