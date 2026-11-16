#!/usr/bin/env bash
# Install (or update) the Haru icon theme for the current user. No sudo needed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LIB="$HOME/.local/share/haru"
STATE="$HOME/.local/state/haru"
CONF="$HOME/.config/haru"
UNITS="$HOME/.config/systemd/user"

# ---- requirements -----------------------------------------------------------
missing=()
command -v python3 >/dev/null || missing+=("python3")
command -v gsettings >/dev/null || missing+=("libglib2.0-bin (gsettings)")
python3 - <<'EOF' 2>/dev/null || missing+=("python3-gi gir1.2-gdkpixbuf-2.0 gir1.2-rsvg-2.0 python3-cairo python3-pil")
import cairo, PIL, gi
gi.require_version("GdkPixbuf", "2.0"); gi.require_version("Rsvg", "2.0")
from gi.repository import GdkPixbuf, Rsvg
EOF
yaru=""
for d in "$HOME/.local/share/icons" /usr/local/share/icons /usr/share/icons; do
    [ -f "$d/Yaru/index.theme" ] && yaru="$d/Yaru"
done
[ -n "$yaru" ] || missing+=("yaru-theme-icon (the Yaru icon theme)")
if [ ${#missing[@]} -gt 0 ]; then
    echo "Haru needs a few things that are not installed:"
    printf '  - %s\n' "${missing[@]}"
    echo "On Ubuntu:  sudo apt install python3-gi gir1.2-gdkpixbuf-2.0 gir1.2-rsvg-2.0 python3-cairo python3-pil yaru-theme-icon"
    exit 1
fi
if ! systemctl --user show-environment >/dev/null 2>&1; then
    echo "Note: no systemd user session found; icons will not update by themselves when apps change."
    NO_UNITS=1
fi

mkdir -p "$LIB" "$STATE" "$CONF" "$UNITS"
systemctl --user stop haru-accent.service 2>/dev/null || true

# remember the theme you had, so uninstall can put it back
current="$(gsettings get org.gnome.desktop.interface icon-theme | tr -d "'")"
if [ "$current" != "Haru" ]; then
    echo "$current" > "$STATE/previous-theme"
fi
[ -f "$STATE/previous-theme" ] || echo "Yaru" > "$STATE/previous-theme"

cp "$HERE/haru.py" "$HERE/config.toml" "$HERE/uninstall.sh" "$HERE/accent-watch.sh" "$LIB/"
rm -rf "$LIB/art" && cp -r "$HERE/art" "$LIB/art"
chmod +x "$LIB/haru.py" "$LIB/uninstall.sh" "$LIB/accent-watch.sh"
# your personal settings start empty: the theme's own look is built in (config.toml)
[ -f "$CONF/config.toml" ] || cp "$HERE/config.user.toml" "$CONF/config.toml"

touch "$STATE/installed"
python3 "$LIB/haru.py" generate --sheet --no-refresh

if [ -z "${NO_UNITS:-}" ]; then
    cp "$HERE/systemd/"haru*.path "$HERE/systemd/"haru*.service "$UNITS/"
    systemctl --user daemon-reload
    systemctl --user enable --now haru.path
fi

# Switch away and back so GNOME Shell rebuilds every app icon. It does not do
# that when only a launcher changes, so launchers that now name a haru- icon
# (snaps, AppImages...) would keep a generic gear. Give it a moment to read the
# new launchers first; hicolor is a neutral stop the accent watcher ignores.
sleep 3
gsettings set org.gnome.desktop.interface icon-theme 'hicolor'
sleep 1
gsettings set org.gnome.desktop.interface icon-theme 'Haru'
if [ -z "${NO_UNITS:-}" ]; then
    systemctl --user enable haru-accent.service
    systemctl --user restart haru-accent.service
fi

echo
echo "Done. Icon theme is now Haru (previous: $(cat "$STATE/previous-theme"))."
echo "Contact sheet: $LIB/contact-sheet.png"
echo "Report:        $LIB/report.txt"
echo "Your settings: $CONF/config.toml"
echo "Uninstall:     $LIB/uninstall.sh"
