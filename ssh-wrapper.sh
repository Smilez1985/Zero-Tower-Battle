#!/bin/bash
# ============================================
# ZERO TOWER BATTLE - SSH Wrapper
# ============================================
# Optional: tmux-basierter Start fuer persistente Sessions.
# Kann in .bashrc STATT des Auto-Start-Blocks eingebunden werden:
#   source ~/battle_game/ssh-wrapper.sh
#
# Standard-Verhalten (install.sh):
#   War Room startet direkt via .bashrc Auto-Start.
#   Dieses Script ist fuer tmux-Modus (optional).
#
# Verhalten:
#   - Wenn tmux-Session "ztb" existiert: attach
#   - Wenn nicht: neue Session starten + War Room laden
#   - Nur bei interaktivem SSH (nicht bei scp/rsync)
# ============================================

# Nur bei interaktivem Terminal (nicht scp/sftp)
if [ -z "$SSH_TTY" ]; then
    return 2>/dev/null || exit 0
fi

# Dynamische Pfade (HOME des eingeloggten Users)
GAME_DIR="${HOME}/battle_game"

# Nur wenn tmux installiert ist
if ! command -v tmux &> /dev/null; then
    echo "[ZTB] tmux nicht installiert. Starte direkt..."
    cd "$GAME_DIR" 2>/dev/null && python3 -u "$GAME_DIR/ui/options/war_room.py"
    return 2>/dev/null || exit 0
fi

# Nicht innerhalb von tmux nochmal attachen
if [ -n "$TMUX" ]; then
    return 2>/dev/null || exit 0
fi

# Session-Name
ZTB_SESSION="ztb"

# Pruefen ob Session existiert
if tmux has-session -t "$ZTB_SESSION" 2>/dev/null; then
    echo "[ZTB] Bestehende Session gefunden. Attaching..."
    exec tmux attach-session -t "$ZTB_SESSION"
else
    echo "[ZTB] Neue Session wird gestartet..."
    exec tmux new-session -s "$ZTB_SESSION" -c "$GAME_DIR" \
        "python3 -u $GAME_DIR/ui/options/war_room.py; bash"
fi
