#!/usr/bin/env bash
# Remove Yaru-Squircle and put back the icon theme you had before. No sudo needed.
set -uo pipefail
LIB="$HOME/.local/share/yaru-squircle"
STATE="$HOME/.local/state/yaru-squircle"
UNITS="$HOME/.config/systemd/user"

systemctl --user disable --now yaru-squircle-accent.service 2>/dev/null
systemctl --user disable --now yaru-squircle.path 2>/dev/null
systemctl --user stop yaru-squircle.service 2>/dev/null
rm -f "$UNITS/yaru-squircle.path" "$UNITS/yaru-squircle.service" "$UNITS/yaru-squircle-accent.service"
systemctl --user daemon-reload

prev="Yaru"
[ -f "$STATE/previous-theme" ] && prev="$(cat "$STATE/previous-theme")"
gsettings set org.gnome.desktop.interface icon-theme "$prev"

# undo launcher changes (only the ones this tool made)
script="$LIB/yaru-squircle.py"
[ -f "$script" ] || script="$(cd "$(dirname "$0")" && pwd)/yaru-squircle.py"
python3 "$script" restore-launchers

rm -rf "$HOME/.local/share/icons/Yaru-Squircle" "$LIB" "$STATE"
echo "Yaru-Squircle removed. Icon theme restored to $prev."
echo "(Your settings in ~/.config/yaru-squircle were kept; delete that folder too if you like.)"
