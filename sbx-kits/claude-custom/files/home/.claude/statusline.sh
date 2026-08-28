#!/usr/bin/env bash
# Claude Code status line for Docker Sandboxes (two lines).
#   line 1:  ~/dir (branch +N -N) · MODEL [effort] · ctx [████░░░░░░] N%/Wk
#   line 2:  hostname · mem U/TG · load L · $COST
# Receives session JSON on stdin. Runs on every render, so each segment stays cheap.

input=$(cat)

# Single jq pass — avoid re-forking jq on every render.
{ read -r dir; read -r model; read -r effort; read -r pct; read -r winsz; read -r cost; } < <(printf '%s' "$input" | jq -r '
  .workspace.current_dir // .cwd // "",
  .model.display_name // "",
  .effort.level // "",
  .context_window.used_percentage // "",
  ((.context_window.context_window_size // 0) / 1000 | floor),
  .cost.total_cost_usd // 0')
[ -z "$dir" ] && dir=$(pwd)

# ANSI colours
RST=$'\033[0m'; BOLD=$'\033[1m'; DIM=$'\033[2m'
CYAN=$'\033[36m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'
GREEN=$'\033[32m'; RED=$'\033[31m'; MAGENTA=$'\033[35m'
WHITE=$'\033[37m'; SEP=$'\033[90m'

# join SEGMENTS... -> non-empty segments separated by " · "
join() {
  local out="" s
  for s in "$@"; do
    [ -z "$s" ] && continue
    if [ -z "$out" ]; then out="$s"; else out="${out}${SEP}${BOLD} · ${RST}${s}"; fi
  done
  printf '%s' "$out"
}

# --- Git branch + added/deleted counts ---
git_seg=""
if branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null); then
  added=$(git -C "$dir" status --porcelain 2>/dev/null | grep -c '^??')
  deleted=$(git -C "$dir" status --porcelain 2>/dev/null | grep -c '^.D')
  changes=""
  [ "$added" -gt 0 ] && changes="${changes}+${added}"
  [ "$deleted" -gt 0 ] && changes="${changes}-${deleted}"
  if [ -n "$changes" ]; then
    git_seg=" ${GREEN}(${branch} ${RED}${changes}${GREEN})${RST}"
  else
    git_seg=" ${GREEN}(${branch})${RST}"
  fi
fi

# --- Model + effort ---
model_seg=""
if [ -n "$model" ]; then
  [ -z "$effort" ] && effort="-"
  model_short="${model/ context/}"
  model_seg="${MAGENTA}${model_short}${DIM} [${effort}]${RST}"
fi

# --- Context battery, colour-coded by fill level; blank early in a session ---
ctx_seg=""
if [ -n "$pct" ] && [ "$pct" != "null" ]; then
  used_int=$(printf '%.0f' "$pct")
  battery_width=10
  filled=$(( used_int * battery_width / 100 ))
  [ "$filled" -gt "$battery_width" ] && filled=$battery_width
  [ "$filled" -lt 0 ] && filled=0
  empty=$(( battery_width - filled ))
  bar=$(printf '%0.s█' $(seq 1 $filled) 2>/dev/null)
  bar="$bar$(printf '%0.s░' $(seq 1 $empty) 2>/dev/null)"
  if   [ "$used_int" -ge 80 ]; then c=$RED
  elif [ "$used_int" -ge 50 ]; then c=$YELLOW
  else c=$GREEN; fi
  ctx_seg="${c}[${bar}] ${used_int}%${DIM}/${winsz}k${RST}"
fi

# --- Memory: prefer cgroup v2 limit, fall back to /proc/meminfo ---
mem_seg=""
if [ -r /sys/fs/cgroup/memory.current ] && [ -r /sys/fs/cgroup/memory.max ]; then
  cur=$(cat /sys/fs/cgroup/memory.current)
  max=$(cat /sys/fs/cgroup/memory.max)
  [ "$max" = "max" ] && max=$(awk '/^MemTotal:/{print $2*1024}' /proc/meminfo)
elif [ -r /proc/meminfo ]; then
  max=$(awk '/^MemTotal:/{print $2*1024}' /proc/meminfo)
  avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo)
  cur=$((max - avail))
fi
if [ -n "$max" ] && [ "$max" -gt 0 ] 2>/dev/null; then
  read -r u t pctm <<<"$(awk -v c="$cur" -v m="$max" \
    'BEGIN{printf "%.1f %.1f %d", c/1073741824, m/1073741824, (c*100)/m}')"
  if   [ "$pctm" -ge 90 ]; then mc=$RED
  elif [ "$pctm" -ge 70 ]; then mc=$YELLOW
  else mc=$CYAN; fi
  mem_seg="${mc}mem ${u}/${t}G${RST}"
fi

# --- CPU 1-min load average ---
load_seg=""
[ -r /proc/loadavg ] && load_seg="${CYAN}load $(awk '{print $1}' /proc/loadavg)${RST}"

# --- Cost ---
cost_seg="${YELLOW}$(printf '$%.2f' "$cost")${RST}"

# Shorten dir: replace $HOME with ~
dir_display="${dir/#$HOME/~}"

line1=$(join "${BLUE}${dir_display}${RST}${git_seg}" "$ctx_seg" "$model_seg")
line2=$(join "${WHITE}${DIM}Sandbox${RST}" "${WHITE}$(hostname)${RST}" "$mem_seg" "$load_seg" "$cost_seg")

printf '%s\n%s\n' "$line1" "$line2"
