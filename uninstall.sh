#!/usr/bin/env bash
# Remove Haru and put back the icon theme you had before. No sudo needed.
set -uo pipefail
LIB="$HOME/.local/share/haru"
STATE="$HOME/.local/state/haru"
UNITS="$HOME/.config/systemd/user"

systemctl --user disable --now haru-accent.service 2>/dev/null
systemctl --user disable --now haru.path 2>/dev/null
systemctl --user stop haru.service 2>/dev/null
rm -f "$UNITS/haru.path" "$UNITS/haru.service" "$UNITS/haru-accent.service"
systemctl --user daemon-reload

prev="Yaru"
[ -f "$STATE/previous-theme" ] && prev="$(cat "$STATE/previous-theme")"
gsettings set org.gnome.desktop.interface icon-theme "$prev"

# undo launcher changes (only the ones this tool made)
script="$LIB/haru.py"
[ -f "$script" ] || script="$(cd "$(dirname "$0")" && pwd)/haru.py"
python3 "$script" restore-launchers

rm -rf "$HOME/.local/share/icons/Haru" "$LIB" "$STATE"
echo "Haru removed. Icon theme restored to $prev."
echo "(Your settings in ~/.config/haru were kept; delete that folder too if you like.)"
