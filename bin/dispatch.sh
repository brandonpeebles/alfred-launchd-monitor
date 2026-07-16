#!/bin/bash
# Launchd Monitor action dispatcher. Receives "<action>:<label>" and runs a single
# launchctl/open call. Never eval's; passes label + resolved paths as discrete argv.
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-$SCRIPT_DIR/launchd_monitor.py}"
LAUNCHCTL="${LAUNCHCTL:-/bin/launchctl}"
DRY="${DISPATCH_DRY_RUN:-0}"
UID_NUM="$(id -u)"
LOG_LINES="${LOG_LINES:-200}"

spec="${1:-}"
action="${spec%%:*}"
label="${spec#*:}"
target="gui/${UID_NUM}/${label}"

run() {
  if [ "$DRY" = "1" ]; then
    echo "+ $*"
  else
    "$@"
  fi
}

notify() {
  [ "$DRY" = "1" ] && { echo "notify: $2"; return 0; }
  "${OSASCRIPT:-osascript}" - "$2" >/dev/null 2>&1 <<'APPLESCRIPT' || true
on run argv
    display notification (item 1 of argv) with title "Launchd Monitor"
end run
APPLESCRIPT
}

die() {
  notify "Launchd Monitor" "✗ $1" || true
  echo "$1" >&2
  exit 1
}

resolve() { python3 "$PY" path "$label" "$1"; }

log_tool_cmd() {
  local path="$1" path_q
  path_q="$(printf '%q' "$path")"
  case "${LOG_TOOL:-tail}" in
    less) echo "less +F ${path_q}" ;;
    lnav)
      if command -v lnav >/dev/null 2>&1; then
        echo "lnav ${path_q}"
      else
        notify "Launchd Monitor" "lnav not installed; using tail"
        echo "tail -n ${LOG_LINES} -F ${path_q}"
      fi ;;
    *) echo "tail -n ${LOG_LINES} -F ${path_q}" ;;
  esac
}

open_terminal() {
  local cmd="$1"
  case "${TERMINAL:-ghostty}" in
    ghostty) run open -na Ghostty --args -e /bin/sh -c "$cmd" ;;
    iterm)
      run osascript - "$cmd" <<'APPLESCRIPT'
on run argv
    tell application "iTerm" to create window with default profile command (item 1 of argv)
end run
APPLESCRIPT
      ;;
    *)
      run osascript - "$cmd" <<'APPLESCRIPT'
on run argv
    tell application "Terminal" to do script (item 1 of argv)
end run
APPLESCRIPT
      ;;
  esac
}

peek_stream() {
  local kind="$1" path
  path="$(resolve "$kind")"
  [ -n "$path" ] || { echo "log path not configured ($kind)"; return 0; }
  if [ -f "$path" ]; then
    echo "==> $path <=="
    tail -n "${LOG_LINES}" "$path"
  else
    echo "log not yet created: $path"
  fi
}

tail_stream() {
  local kind="$1" path cmd
  path="$(resolve "$kind")"
  [ -n "$path" ] || die "log path not configured ($kind)"
  cmd="$(log_tool_cmd "$path")"
  open_terminal "$cmd"
  notify "Launchd Monitor" "📟 Tailing ${kind} for ${label}"
}

case "$action" in
  restart)
    run "$LAUNCHCTL" kickstart -k "$target" && notify "Launchd Monitor" "↻ Restarted ${label}" || die "restart failed: ${label}" ;;
  unload)
    run "$LAUNCHCTL" bootout "$target" && notify "Launchd Monitor" "⏏ Unloaded ${label}" || die "unload failed: ${label}" ;;
  load)
    plist="$(resolve plist)"
    [ -n "$plist" ] || die "No plist found for ${label}"
    run "$LAUNCHCTL" bootstrap "gui/${UID_NUM}" "$plist" && notify "Launchd Monitor" "⏵ Loaded ${label}" || die "load failed: ${label}" ;;
  enable)
    run "$LAUNCHCTL" enable "$target" && notify "Launchd Monitor" "✓ Enabled ${label}" || die "enable failed: ${label}" ;;
  disable)
    run "$LAUNCHCTL" disable "$target" && notify "Launchd Monitor" "🚫 Disabled ${label}" || die "disable failed: ${label}" ;;
  peek)      peek_stream "${LOG_STREAM:-out}" ;;
  peek-out)  peek_stream out ;;
  peek-err)  peek_stream err ;;
  tail-term)     tail_stream "${LOG_STREAM:-out}" ;;
  tail-term-out) tail_stream out ;;
  tail-term-err) tail_stream err ;;
  reveal-out) p="$(resolve out)"; [ -n "$p" ] || die "no stdout path"; run open -R "$p" ;;
  reveal-err) p="$(resolve err)"; [ -n "$p" ] || die "no stderr path"; run open -R "$p" ;;
  open-plist) p="$(resolve plist)"; [ -n "$p" ] || die "no plist path"; run open -t "$p" ;;
  copy-label)
    if [ "$DRY" = "1" ]; then echo "+ pbcopy ${label}"; else printf '%s' "$label" | pbcopy; fi
    notify "Launchd Monitor" "Copied label" ;;
  copy-logpath-out)
    p="$(resolve out)"; [ -n "$p" ] || die "no stdout path"
    if [ "$DRY" = "1" ]; then echo "+ pbcopy ${p}"; else printf '%s' "$p" | pbcopy; fi ;;
  copy-logpath-err)
    p="$(resolve err)"; [ -n "$p" ] || die "no stderr path"
    if [ "$DRY" = "1" ]; then echo "+ pbcopy ${p}"; else printf '%s' "$p" | pbcopy; fi ;;
  *) die "Unknown action: ${action}" ;;
esac
