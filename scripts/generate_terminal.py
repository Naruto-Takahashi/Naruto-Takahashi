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


def cmd_prompt(x, y, cmd):
    # Starship の character モジュール (secondary色の ❯) を模した実行済みコマンド行
    return (
        f'<text x="{x}" y="{y}" class="cmdline">'
        f'<tspan class="promptchar" font-weight="bold">&#10095;</tspan> {esc(cmd)}'
        f'</text>'
    )


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
rows.append(text(LEFT, y, "dim", "-" * 78))

y += 36
rows.append(cmd_prompt(LEFT, y, "whoami"))
for key, value in [
    ("Role", identity.get("role", "")),
    ("University", identity.get("university", "")),
    ("Lab", identity.get("lab", "")),
    ("Location", identity.get("location", "")),
]:
    y += 28 if key == "Role" else LINE_H
    rows.append(text(LEFT, y, "mono", f"{key:<11} {value}"))

y += 40
rows.append(cmd_prompt(LEFT, y, "research --current"))
for item in research.get("current", []):
    y += LINE_H
    status = item.get("status", "").upper()
    label = item.get("label", "")
    rows.append(text(LEFT, y, status_class(status), f"[{status}] {label}"))

description = research.get("description", [])
if description:
    y += 40
    rows.append(cmd_prompt(LEFT, y, "cat research.txt"))
    for line in description:
        y += LINE_H
        rows.append(text(LEFT, y, "mono", line))

if stack:
    y += 40
    rows.append(cmd_prompt(LEFT, y, "stack --list"))
    y += 28
    rows.append(text(LEFT, y, "mono", " · ".join(stack)))

if systems:
    y += 40
    rows.append(cmd_prompt(LEFT, y, "env --list"))
    y += 28
    rows.append(text(LEFT, y, "mono", f'{"OS":<8} {" · ".join(systems.get("os", []))}'))
    y += LINE_H
    rows.append(text(LEFT, y, "mono", f'{"Editor":<8} {systems.get("editor", "")}'))
    y += LINE_H
    rows.append(text(LEFT, y, "mono", f'{"WM":<8} {systems.get("wm", "")}'))

if projects:
    y += 40
    rows.append(cmd_prompt(LEFT, y, "projects --active"))
    y += 28
    rows.append(text(LEFT, y, "dim", f'{"PID":<5} {"PROJECT":<31} STATUS'))
    for project in projects:
        y += LINE_H
        rows.append(text(
            LEFT, y, "mono",
            f'{project.get("pid",""):<5} {project.get("name",""):<31} {project.get("status","")}'
        ))

body_bottom = y + 30

# --- Starship 風 powerline プロンプト (下部バー) ---
# セグメント構成: nixcli_badge(tertiary) -> directory(accent) -> git_branch/status(dark) -> character
PROMPT_H = 24
prompt_y_top = body_bottom + 10
prompt_baseline = prompt_y_top + PROMPT_H / 2 + 4
bar_bottom = prompt_y_top + PROMPT_H

badge_text = f' {prompt.get("badge", "")} '
dir_text = f' {prompt.get("path", "")} '
git_text = f' {prompt.get("branch", "")} '

CHAR_W = 6.2
PAD = 4
ARROW_W = 8  # powerline矢印の突き出し幅

def seg_width(s):
    return round(len(s) * CHAR_W) + PAD * 2

# セグメント定義: (表示文字, 背景色, 文字色)
segments = [
    (badge_text, TERTIARY, ON_ACCENT),
    (dir_text, ACCENT, ON_ACCENT),
    (git_text, DARK, ACCENT),
]

seg_x = LEFT
rect_svg = []
arrow_svg = []
seg_text_svg = []
bounds = []
for value, bg_color, fg_color in segments:
    w = seg_width(value)
    rect_svg.append(f'<rect x="{seg_x}" y="{prompt_y_top}" width="{w}" height="{PROMPT_H}" fill="{bg_color}"/>')
    seg_text_svg.append(
        f'<text x="{seg_x + w/2}" y="{prompt_baseline}" class="promptseg" '
        f'text-anchor="middle" fill="{fg_color}" font-weight="bold">{esc(value)}</text>'
    )
    bounds.append(seg_x + w)
    seg_x += w

# powerline矢印: 各セグメント境界に、手前の色で右向き三角形を重ね描きする
# (先に全セグメントのrectを描画してから矢印を上に重ねることで、次のセグメントに
#  食い込む矢印が隠れずに見える)
for boundary, (_, bg_color, _) in zip(bounds, segments):
    th = PROMPT_H / 2
    arrow_svg.append(
        f'<polygon points="{boundary},{prompt_y_top} {boundary+ARROW_W},{prompt_y_top+th} '
        f'{boundary},{bar_bottom}" fill="{bg_color}"/>'
    )

arrow_x = seg_x + ARROW_W + 8
prompt_svg = rect_svg + arrow_svg + seg_text_svg
prompt_svg.append(
    f'<text x="{arrow_x}" y="{prompt_baseline}" class="promptseg" fill="{SECONDARY}" '
    f'font-weight="bold">&#10095;</text>'
)
prompt_svg.append(
    f'<rect x="{arrow_x + 14}" y="{prompt_baseline - 11}" width="6" height="13" rx="1" class="cursor"/>'
)

height = bar_bottom + 16

# --- タブバー (信号ボタン行 + タブ行の2段構成) ---
DOT_ROW_H = 30
TAB_ROW_H = 26
HEADER_H = DOT_ROW_H + TAB_ROW_H
tab_label = "zsh"
tab_w = round(len(tab_label) * 7.2) + 26
tab_x = 16
tab_skew = 7

svg = f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    text {{ font-family: {FONT}; }}
    .bg {{ fill: {BG}; }}
    .border {{ stroke: {BORDER}; stroke-width: 1.5; }}
    .mono {{ font-size: 14px; fill: {FG}; }}
    .title {{ font-size: 16px; font-weight: 700; fill: {ACCENT}; }}
    .cmdline {{ font-size: 14px; fill: {FG}; }}
    .promptchar {{ fill: {SECONDARY}; }}
    .dim {{ font-size: 14px; fill: {DIM}; }}
    .green {{ font-size: 14px; fill: {DRAGON_GREEN}; }}
    .yellow {{ font-size: 14px; fill: {DRAGON_YELLOW}; }}
    .accent {{ font-size: 14px; fill: {ACCENT}; }}
    .tabtext {{ font-size: 12px; fill: {ON_ACCENT}; font-weight: 700; }}
    .promptseg {{ font-size: 12px; }}
    .cursor {{ fill: {CARET}; animation: blink 1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
  </style>

  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" class="bg border"/>

  <path d="M 0.75 12.75 Q 0.75 0.75 12.75 0.75 L {WIDTH-12.75} 0.75 Q {WIDTH-0.75} 0.75 {WIDTH-0.75} 12.75
           L {WIDTH-0.75} {HEADER_H} L 0.75 {HEADER_H} Z" fill="{BG_ALT}"/>
  <line x1="0.75" y1="{DOT_ROW_H}" x2="{WIDTH-0.75}" y2="{DOT_ROW_H}" stroke="{BORDER}" stroke-width="1"/>

  <circle cx="24" cy="{DOT_ROW_H/2}" r="6" fill="{DRAGON_RED}"/>
  <circle cx="45" cy="{DOT_ROW_H/2}" r="6" fill="{DRAGON_YELLOW}"/>
  <circle cx="66" cy="{DOT_ROW_H/2}" r="6" fill="{DRAGON_GREEN}"/>

  <polygon points="{tab_x},{DOT_ROW_H} {tab_x+tab_skew},{HEADER_H} {tab_x+tab_w+tab_skew},{HEADER_H} {tab_x+tab_w},{DOT_ROW_H}" fill="{ACCENT}"/>
  {text(tab_x + tab_w/2 + tab_skew/2, DOT_ROW_H + TAB_ROW_H*0.68, "tabtext", tab_label, anchor="middle")}

  {"".join(rows)}

  {"".join(prompt_svg)}
</svg>
"""

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(svg, encoding="utf-8")
print(f"Generated {OUTPUT_PATH}")
