#!/usr/bin/env python3
"""profile.json から WezTerm/Starship/Kanagawa Dragon 風のターミナルSVGを生成する。

配色は nix-config の実設定から抽出した値を使用:
  - modules/apps/bat/kanagawa-dragon.tmTheme (背景・前景・コメント色)
  - modules/apps/wezterm/wezterm.lua (フォールバックのMatugenアクセント色)
  - modules/shell/starship/starship.toml (プロンプトのセグメント構成)
"""
from pathlib import Path
from html import escape
import json

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "assets" / "terminal.svg"

WIDTH = 900
LEFT = 34
LINE_H = 24

FONT = ('"HackGen Console NF", "SFMono-Regular", "Cascadia Code", '
        '"Roboto Mono", Menlo, Consolas, monospace')

# Kanagawa Dragon (実測値: kanagawa-dragon.tmTheme)
BG = "#181616"
BG_ALT = "#1d1c19"      # タブバー相当 (bg寄りの濃色)
FG = "#c5c9c5"
DIM = "#737c73"         # コメント色
BORDER = "#282727"
CARET = "#c8c093"
DRAGON_GREEN = "#87a987"
DRAGON_YELLOW = "#c4b28a"
DRAGON_RED = "#c4746e"

# WezTerm/Starship フォールバック Matugen パレット
ACCENT = "#a2c9fd"
ON_ACCENT = "#111418"
TERTIARY = "#d7bde4"
SECONDARY = "#bbc7db"
MUTED = "#c3c6cf"
DARK = "#272a2f"


def esc(s):
    return escape(str(s))


def text(x, y, cls, value, anchor=None, weight=None):
    attrs = f' text-anchor="{anchor}"' if anchor else ""
    if weight:
        attrs += f' font-weight="{weight}"'
    return f'<text x="{x}" y="{y}" class="{cls}"{attrs}>{esc(value)}</text>'


def status_class(status):
    return {
        "RUNNING": "green",
        "READING": "yellow",
        "PAUSED": "dim",
        "DONE": "accent",
    }.get(status.upper(), "mono")


with PROFILE_PATH.open(encoding="utf-8") as f:
    p = json.load(f)

identity = p["identity"]
systems = p.get("systems", {})
research = p.get("research", {})
projects = p.get("projects", [])
stack = p.get("stack", [])
prompt = p.get("prompt", {})

rows = []
y = 74

rows.append(text(LEFT, y, "title", f'{identity["username"]}@{identity["terminal_host"]}'))
y += 26
rows.append(text(LEFT, y, "dim", "─" * 78))

y += 36
rows.append(text(LEFT, y, "prompt", "$ whoami"))
for key, value in [
    ("Role", identity.get("role", "")),
    ("University", identity.get("university", "")),
    ("Lab", identity.get("lab", "")),
    ("Location", identity.get("location", "")),
]:
    y += 28 if key == "Role" else LINE_H
    rows.append(text(LEFT, y, "mono", f"{key:<11} {value}"))

y += 40
rows.append(text(LEFT, y, "prompt", "$ research --current"))
for item in research.get("current", []):
    y += LINE_H
    status = item.get("status", "").upper()
    label = item.get("label", "")
    rows.append(text(LEFT, y, status_class(status), f"[{status}] {label}"))

description = research.get("description", [])
if description:
    y += 40
    rows.append(text(LEFT, y, "prompt", "$ cat research.txt"))
    for line in description:
        y += LINE_H
        rows.append(text(LEFT, y, "mono", line))

if stack:
    y += 40
    rows.append(text(LEFT, y, "prompt", "$ stack --list"))
    y += 28
    rows.append(text(LEFT, y, "mono", " · ".join(stack)))

if systems:
    y += 40
    rows.append(text(LEFT, y, "prompt", "$ env --list"))
    y += 28
    rows.append(text(LEFT, y, "mono", f'{"OS":<8} {" · ".join(systems.get("os", []))}'))
    y += LINE_H
    rows.append(text(LEFT, y, "mono", f'{"Editor":<8} {systems.get("editor", "")}'))
    y += LINE_H
    rows.append(text(LEFT, y, "mono", f'{"WM":<8} {systems.get("wm", "")}'))

if projects:
    y += 40
    rows.append(text(LEFT, y, "prompt", "$ projects --active"))
    y += 28
    rows.append(text(LEFT, y, "dim", f'{"PID":<5} {"PROJECT":<31} STATUS'))
    for project in projects:
        y += LINE_H
        rows.append(text(
            LEFT, y, "mono",
            f'{project.get("pid",""):<5} {project.get("name",""):<31} {project.get("status","")}'
        ))

body_bottom = y + 30
cursor_y = y - 14

# --- Starship 風 powerline プロンプト (下部バー) ---
# セグメント構成: nixcli_badge(tertiary) -> directory(accent) -> git_branch/status(dark) -> character
PROMPT_H = 40
prompt_y_top = body_bottom + 16
prompt_baseline = prompt_y_top + 26
bar_bottom = prompt_y_top + PROMPT_H

badge_text = f' {prompt.get("badge", "")} '
dir_text = f' {prompt.get("path", "")} '
git_text = f' {prompt.get("branch", "")} '

def seg_width(s):
    return int(len(s) * 8.6) + 20

x = LEFT
segs = []

w1 = seg_width(badge_text)
segs.append(("rect", x, w1, TERTIARY))
segs.append(("text", x + w1 / 2, badge_text, ON_ACCENT, "bold"))
x += w1
segs.append(("tri", x, TERTIARY, ACCENT))

w2 = seg_width(dir_text)
segs.append(("rect", x, w2, ACCENT))
segs.append(("text", x + w2 / 2, dir_text, ON_ACCENT, "bold"))
x += w2
segs.append(("tri", x, ACCENT, DARK))

w3 = seg_width(git_text)
segs.append(("rect", x, w3, DARK))
segs.append(("text", x + w3 / 2, f" {git_text}", ACCENT, "normal"))
x += w3
segs.append(("tri", x, DARK, BG))

prompt_svg = []
for seg in segs:
    if seg[0] == "rect":
        _, sx, sw, color = seg
        prompt_svg.append(
            f'<rect x="{sx}" y="{prompt_y_top}" width="{sw}" height="{PROMPT_H}" fill="{color}"/>'
        )
    elif seg[0] == "text":
        _, cx, value, color, weight = seg
        prompt_svg.append(
            f'<text x="{cx}" y="{prompt_baseline}" class="promptseg" '
            f'text-anchor="middle" fill="{color}" font-weight="{weight}">{esc(value)}</text>'
        )
    elif seg[0] == "tri":
        _, tx, from_color, to_color = seg
        th = PROMPT_H / 2
        prompt_svg.append(
            f'<polygon points="{tx},{prompt_y_top} {tx+14},{prompt_y_top+th} {tx},{bar_bottom}" '
            f'fill="{from_color}"/>'
        )

arrow_x = x + 16
prompt_svg.append(
    f'<text x="{arrow_x}" y="{prompt_baseline}" class="promptseg" fill="{SECONDARY}" '
    f'font-weight="bold">❯</text>'
)
prompt_svg.append(
    f'<rect x="{arrow_x + 22}" y="{prompt_baseline - 15}" width="8" height="17" rx="1" class="cursor"/>'
)

height = bar_bottom + 26

# --- タブバー (WezTerm 風の平行四辺形タブ) ---
TAB_H = 34
tab_label = " zsh "
tab_w = int(len(tab_label) * 8.4) + 24
tab_x = 96

svg = f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    text {{ font-family: {FONT}; }}
    .bg {{ fill: {BG}; }}
    .border {{ stroke: {BORDER}; stroke-width: 1.5; }}
    .mono {{ font-size: 14px; fill: {FG}; }}
    .title {{ font-size: 16px; font-weight: 700; fill: {ACCENT}; }}
    .prompt {{ font-size: 14px; font-weight: 700; fill: {DRAGON_GREEN}; }}
    .dim {{ font-size: 14px; fill: {DIM}; }}
    .green {{ font-size: 14px; fill: {DRAGON_GREEN}; }}
    .yellow {{ font-size: 14px; fill: {DRAGON_YELLOW}; }}
    .accent {{ font-size: 14px; fill: {ACCENT}; }}
    .tabtext {{ font-size: 13px; fill: {ON_ACCENT}; font-weight: 700; }}
    .promptseg {{ font-size: 14px; }}
    .cursor {{ fill: {CARET}; animation: blink 1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
  </style>

  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" class="bg border"/>

  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{TAB_H}" rx="12" fill="{BG_ALT}"/>
  <rect x="0.75" y="{TAB_H/2}" width="{WIDTH-1.5}" height="{TAB_H/2}" fill="{BG_ALT}"/>
  <circle cx="24" cy="{TAB_H/2+0.75}" r="6" fill="{DRAGON_RED}"/>
  <circle cx="45" cy="{TAB_H/2+0.75}" r="6" fill="{DRAGON_YELLOW}"/>
  <circle cx="66" cy="{TAB_H/2+0.75}" r="6" fill="{DRAGON_GREEN}"/>

  <polygon points="{tab_x},1 {tab_x+10},{TAB_H} {tab_x+tab_w+10},{TAB_H} {tab_x+tab_w},1" fill="{ACCENT}"/>
  {text(tab_x + tab_w/2 + 5, TAB_H*0.66, "tabtext", tab_label, anchor="middle")}

  {"".join(rows)}

  {"".join(prompt_svg)}
</svg>
"""

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(svg, encoding="utf-8")
print(f"Generated {OUTPUT_PATH}")
