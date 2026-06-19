#!/bin/bash
#
# VoiceSnip post-install: Wayland input setup
# ===========================================
# Grants the permissions VoiceSnip needs for global hotkeys + text insertion
# under Wayland:
#   1. Membership in group 'input'  -> read /dev/input/event* (evdev hotkey)
#   2. udev rule for /dev/uinput    -> ydotool can inject text without root
#
# Design constraints (see project memory wayland-hotkey-architecture):
#   - Only acts under Wayland; on X11 it skips silently.
#   - Idempotent: if everything is already set up, it does nothing.
#   - Transparent: explains exactly what needs sudo and why, then either runs
#     it (sudo prompts for the password) or, on opt-out / no TTY, just prints
#     the commands for the user to run manually.
#   - Never hard-fails: always exits 0 so it cannot abort the installation.
#
# NOTE on I/O: the quickstrap installer runs post-install scripts with their
# stdout/stderr CAPTURED (shown only after the script exits). Plain echo would
# therefore be invisible and an interactive prompt would hang silently. So all
# user-facing interaction goes to the controlling terminal (/dev/tty), which
# bypasses that capture. The ydotoold daemon is not managed here -- VoiceSnip
# starts it on demand.

set -u

RULES_NAME="99-voicesnip-uinput.rules"
RULES_DEST="/etc/udev/rules.d/${RULES_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_SRC="${SCRIPT_DIR}/${RULES_NAME}"
TARGET_USER="${SUDO_USER:-$(id -un)}"

# --- Terminal I/O (bypasses the installer's output capture) -----------------
if { true >/dev/tty; } 2>/dev/null; then
    TTY=/dev/tty
else
    TTY=""
fi

say() {  # visible to the user via the terminal; falls back to stdout (log)
    if [ -n "$TTY" ]; then printf '%s\n' "$*" >"$TTY"; else printf '%s\n' "$*"; fi
}

# --- 1. Only relevant under Wayland -----------------------------------------
if [ "${XDG_SESSION_TYPE:-}" != "wayland" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "Not a Wayland session - skipping Wayland input setup (X11 uses xdotool)."
    exit 0
fi

# --- 2. Idempotency: what is still missing? ---------------------------------
# Two distinct notions of membership:
#   in_db      -> recorded in the group database (/etc/group) after usermod
#   in_session -> active in THIS login session's process credentials
# They diverge right after a usermod: the database is updated immediately, but
# the running session keeps its old groups until the user logs out and back in.
# This script escalates per-command via sudo, so it runs as TARGET_USER and its
# own `id -nG` (no args) reflects that user's live session -- which is exactly
# what VoiceSnip inherits when launched from the desktop.
in_db=false
if id -nG "$TARGET_USER" 2>/dev/null | tr ' ' '\n' | grep -qx input; then
    in_db=true
fi

in_session=false
if [ "$(id -un)" = "$TARGET_USER" ] \
   && id -nG 2>/dev/null | tr ' ' '\n' | grep -qx input; then
    in_session=true
fi

need_group=true
$in_db && need_group=false

need_rule=true
if [ -f "$RULES_DEST" ]; then
    need_rule=false
fi

if ! $need_group && ! $need_rule; then
    # Configured in the database. If this session has not picked the group up
    # yet, that is precisely why VoiceSnip still cannot read the keyboard --
    # tell the user to re-login instead of falsely reporting "all good".
    if $in_db && ! $in_session && [ "$(id -un)" = "$TARGET_USER" ]; then
        say ""
        say "================================================================"
        say " VoiceSnip: Wayland input"
        say "================================================================"
        say "Your user IS in the 'input' group, but your CURRENT session"
        say "started before that change and has not picked it up yet."
        say ""
        say "  -> Log out and back in (or reboot), then start VoiceSnip."
        say ""
        say "(Quick test without re-login:  sg input -c ./start.sh )"
        echo "Wayland input configured; pending re-login for 'input' group."
    else
        echo "Wayland input already configured (user in 'input' group, udev rule present)."
    fi
    exit 0
fi

# --- 3. Build the list of sudo commands needed ------------------------------
declare -a CMDS=()
say ""
say "================================================================"
say " VoiceSnip: Wayland input setup"
say "================================================================"
say "The following one-time changes are needed and require sudo:"
say ""
if $need_group; then
    say "  • Add user '$TARGET_USER' to group 'input'"
    say "      -> lets VoiceSnip read keyboard events for the global hotkey"
    CMDS+=("usermod -aG input $TARGET_USER")
fi
if $need_rule; then
    say "  • Install udev rule for /dev/uinput"
    say "      -> lets ydotool insert transcribed text without running as root"
    CMDS+=("install -m 0644 '$RULES_SRC' '$RULES_DEST'")
    CMDS+=("udevadm control --reload-rules")
    CMDS+=("udevadm trigger --subsystem-match=misc --sysname-match=uinput")
    CMDS+=("modprobe uinput")
fi
say ""

print_manual() {
    say "Run these commands yourself, then log out and back in:"
    for c in "${CMDS[@]}"; do
        say "    sudo $c"
    done
}

run_with_sudo() {
    if ! command -v sudo >/dev/null 2>&1; then
        say "  sudo not found - please run the commands above as root."
        print_manual
        return 1
    fi
    say "  Applying now - sudo will ask for YOUR login password:"
    for c in "${CMDS[@]}"; do
        say "    -> sudo $c"
        # Run sudo against the terminal so its password prompt is visible and
        # can read input even though the installer captured our stdout/stderr.
        if [ -n "$TTY" ]; then
            # shellcheck disable=SC2086
            if ! eval "sudo $c" <"$TTY" >"$TTY" 2>&1; then
                say "  ! Command failed: sudo $c"
                print_manual
                return 1
            fi
        else
            # shellcheck disable=SC2086
            if ! eval "sudo $c"; then
                say "  ! Command failed: sudo $c"
                print_manual
                return 1
            fi
        fi
    done
    return 0
}

# --- 4. Ask (only if we have a terminal), execute or print ------------------
applied=false
if [ -n "$TTY" ]; then
    printf 'Apply these changes automatically now? [Y/n] ' >"$TTY"
    read -r ans <"$TTY" || ans=""
    case "${ans:-Y}" in
        [Nn]*) print_manual ;;
        *)     run_with_sudo && applied=true || true ;;
    esac
else
    # No terminal (e.g. piped installer) - never block, just show commands.
    print_manual
fi

# --- 5. Closing notes (never fail) ------------------------------------------
say ""
if $applied; then
    say "  ✓ Wayland input setup applied."
    if $need_group; then
        say "  NOTE: group changes take effect after the next login."
        say "        Log out and back in before using the hotkey."
    fi
fi
exit 0
