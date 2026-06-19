#!/bin/bash
#
# VoiceSnip uninstall: Wayland input teardown
# ===========================================
# Reverses the out-of-tree side effects that setup_wayland_input.sh created.
# quickstrap removes the project-owned parts (venv, generated files) on its own;
# this script only undoes what the post-install script wrote OUTSIDE the project:
#   1. udev rule /etc/udev/rules.d/99-voicesnip-uinput.rules
#   2. membership of the install user in group 'input'
#
# Both side effects are deterministic (fixed rule name, known user), so they are
# recomputed here from the environment - no recorded state file is needed.
#
# Design constraints (mirrors setup_wayland_input.sh):
#   - Idempotent: removes only what is still present; if nothing is left, does
#     nothing. Session-type independent (works from X11 or Wayland) - the side
#     effects themselves are not tied to the session.
#   - Transparent: explains exactly what needs sudo and why, then either runs it
#     (sudo prompts for the password) or, on opt-out / no TTY, prints the commands
#     for the user to run manually.
#   - Never hard-fails: always exits 0 so it cannot abort the uninstall.
#
# NOTE on I/O: quickstrap runs lifecycle scripts (post-install AND uninstall) with
# their stdout/stderr CAPTURED (shown only after the script exits). Plain echo
# would therefore be invisible and an interactive prompt would hang silently. So
# all user-facing interaction goes to the controlling terminal (/dev/tty), which
# bypasses that capture - exactly as the matching setup script does.

set -u

RULES_NAME="99-voicesnip-uinput.rules"
RULES_DEST="/etc/udev/rules.d/${RULES_NAME}"
# Same user resolution as the setup script: the real login user, even under sudo.
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

# --- 1. What is still present and needs undoing? ----------------------------
remove_group=false
if id -nG "$TARGET_USER" 2>/dev/null | tr ' ' '\n' | grep -qx input; then
    remove_group=true
fi

remove_rule=false
if [ -f "$RULES_DEST" ]; then
    remove_rule=true
fi

if ! $remove_group && ! $remove_rule; then
    echo "No Wayland input changes to undo (no udev rule, user not in 'input' group)."
    exit 0
fi

# --- 2. Build the list of sudo commands needed ------------------------------
declare -a CMDS=()
say ""
say "================================================================"
say " VoiceSnip: Wayland input teardown"
say "================================================================"
say "The following changes made during installation will be reverted"
say "(this requires sudo):"
say ""
if $remove_rule; then
    say "  • Remove udev rule $RULES_DEST"
    say "      -> the /dev/uinput permission grant for ydotool is no longer needed"
    CMDS+=("rm -f '$RULES_DEST'")
    CMDS+=("udevadm control --reload-rules")
    CMDS+=("udevadm trigger --subsystem-match=misc --sysname-match=uinput")
fi
if $remove_group; then
    say "  • Remove user '$TARGET_USER' from group 'input'"
    say "      -> revokes the keyboard-event read access VoiceSnip needed"
    say "      NOTE: only do this if no other tool relies on 'input' membership"
    CMDS+=("gpasswd -d $TARGET_USER input")
fi
say ""

print_manual() {
    say "Run these commands yourself to finish the teardown:"
    for c in "${CMDS[@]}"; do
        say "    sudo $c"
    done
    if $remove_group; then
        say "(group changes take effect after the next login)"
    fi
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

# --- 3. Ask (only if we have a terminal), execute or print ------------------
reverted=false
if [ -n "$TTY" ]; then
    printf 'Revert these changes automatically now? [Y/n] ' >"$TTY"
    read -r ans <"$TTY" || ans=""
    case "${ans:-Y}" in
        [Nn]*) print_manual ;;
        *)     run_with_sudo && reverted=true || true ;;
    esac
else
    # No terminal (e.g. piped installer) - never block, just show commands.
    print_manual
fi

# --- 4. Closing notes (never fail) ------------------------------------------
say ""
if $reverted; then
    say "  ✓ Wayland input changes reverted."
    if $remove_group; then
        say "  NOTE: group changes take effect after the next login."
    fi
fi
exit 0
