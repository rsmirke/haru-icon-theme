#!/usr/bin/env bash
# Install (or update) the Yaru-Squircle icon theme for the current user. No sudo needed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LIB="$HOME/.local/share/yaru-squircle"
STATE="$HOME/.local/state/yaru-squircle"
CONF="$HOME/.config/yaru-squircle"
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
    echo "Yaru-Squircle needs a few things that are not installed:"
    printf '  - %s\n' "${missing[@]}"
    echo "On Ubuntu:  sudo apt install python3-gi gir1.2-gdkpixbuf-2.0 gir1.2-rsvg-2.0 python3-cairo python3-pil yaru-theme-icon"
    exit 1
fi
if ! systemctl --user show-environment >/dev/null 2>&1; then
    echo "Note: no systemd user session found; icons will not update by themselves when apps change."
    NO_UNITS=1
fi

mkdir -p "$LIB" "$STATE" "$CONF" "$UNITS"
systemctl --user stop yaru-squircle-accent.service 2>/dev/null || true

# remember the theme you had, so uninstall can put it back
current="$(gsettings get org.gnome.desktop.interface icon-theme | tr -d "'")"
if [ "$current" != "Yaru-Squircle" ]; then
    echo "$current" > "$STATE/previous-theme"
fi
[ -f "$STATE/previous-theme" ] || echo "Yaru" > "$STATE/previous-theme"

cp "$HERE/yaru-squircle.py" "$HERE/config.toml" "$HERE/uninstall.sh" "$HERE/accent-watch.sh" "$LIB/"
rm -rf "$LIB/art" && cp -r "$HERE/art" "$LIB/art"
chmod +x "$LIB/yaru-squircle.py" "$LIB/uninstall.sh" "$LIB/accent-watch.sh"
# your personal settings start empty: the theme's own look is built in (config.toml)
[ -f "$CONF/config.toml" ] || cp "$HERE/config.user.toml" "$CONF/config.toml"

touch "$STATE/installed"
python3 "$LIB/yaru-squircle.py" generate --sheet

if [ -z "${NO_UNITS:-}" ]; then
    cp "$HERE/systemd/"yaru-squircle*.path "$HERE/systemd/"yaru-squircle*.service "$UNITS/"
    systemctl --user daemon-reload
    systemctl --user enable --now yaru-squircle.path
fi

# switch away and back so GNOME Shell drops any icons it had cached
gsettings set org.gnome.desktop.interface icon-theme "$(cat "$STATE/previous-theme")"
sleep 1
gsettings set org.gnome.desktop.interface icon-theme 'Yaru-Squircle'
if [ -z "${NO_UNITS:-}" ]; then
    systemctl --user enable yaru-squircle-accent.service
    systemctl --user restart yaru-squircle-accent.service
fi

echo
echo "Done. Icon theme is now Yaru-Squircle (previous: $(cat "$STATE/previous-theme"))."
echo "Contact sheet: $LIB/contact-sheet.png"
echo "Report:        $LIB/report.txt"
echo "Your settings: $CONF/config.toml"
echo "Uninstall:     $LIB/uninstall.sh"
