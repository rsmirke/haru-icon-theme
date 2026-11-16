#!/usr/bin/env bash
# When the accent colour is changed in Settings, Ubuntu switches the icon theme
# to plain Yaru-<accent>. This rebuilds Haru on top of the new variant
# and switches back to it, so the squircles survive accent changes.
LIB="$HOME/.local/share/haru"
STATE="$HOME/.local/state/haru"
gsettings monitor org.gnome.desktop.interface icon-theme | while read -r _ value; do
    theme="$(echo "$value" | tr -d "'")"
    case "$theme" in
        Haru) ;;
        Yaru|Yaru-*)
            echo "accent changed: rebuilding on $theme"
            echo "$theme" > "$STATE/previous-theme"
            python3 "$LIB/haru.py" generate
            gsettings set org.gnome.desktop.interface icon-theme 'Haru'
            ;;
    esac
done
