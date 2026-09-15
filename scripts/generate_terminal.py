#!/usr/bin/env python3
"""profile.json から WezTerm/Starship/Kanagawa Dragon 風のターミナルSVGを生成する。

配色は nix-config の実設定から抽出した値を使用:
  - modules/apps/bat/kanagawa-dragon.tmTheme (背景・前景・コメント色)
  - modules/apps/wezterm/wezterm.lua (フォールバックのMatugenアクセント色)
  - modules/shell/starship/starship.toml (プロンプトのセグメント構成)

GitHub の README は <img src="assets/terminal.svg"> でこのファイルを直接
参照する (camoプロキシを経由せず raw のまま配信される) ため、CSSの
@keyframesアニメーションはそのまま閲覧者のブラウザで再生される
(ただしJS/:hover等のインタラクションは img コンテキストでは無効)。
これを利用して、コマンドブロックが上から順にタイプされるように
出現する一度きりの再生演出と、常時ループするスキャンライン演出を付けている。
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

# --- 実際の starship.toml (modules/shell/starship/starship.toml) の format:
#   $directory -> [](fg:accent bg:dark) -> $git_branch$git_status -> [](fg:dark) -> \n$character
#   right_format = "$cmd_duration$time"
# 実機では各コマンド実行のたびにこのプロンプトブロックが表示される
# (1回だけ末尾に出るのではない) ため、コマンド行ごとに描画する。
# git_branch の symbol は U+F418 (nf-oct-git_branch)、cmd_duration/time の
# 区切りアイコンは U+E0B3 (powerline的な小さな山形) を実設定のまま焼き込む。
GIT_BRANCH_ICON = ""
SEGMENT_ICON = ""

# バー自体は実機のように細く (フォントサイズ・パディングを本文より一段階小さく)
BAR_H = 15
BAR_FONT = 10
BAR_CHAR_W = 5.1
BAR_PAD = 3
ARROW_W = 6
BAR_TO_CMD_GAP = 22
CMD_TO_NEXT_BAR_GAP = 30

# ブロックごとの再生ディレイ (「タイピング再生」演出)。ブロック数に応じて
# 均等に増分するだけの簡易版。1ブロック = 1コマンド行+その出力ぶん。
BLOCK_DELAY_STEP = 0.55
TYPE_DELAY_OFFSET = 0.12


def esc(s):
    return escape(str(s))


def text(x, y, cls, value, anchor=None, weight=None):
    attrs = f' text-anchor="{anchor}"' if anchor else ""
    if weight:
        attrs += f' font-weight="{weight}"'
    return f'<text x="{x}" y="{y}" class="{cls}"{attrs}>{esc(value)}</text>'


def kv_row(x, value_x, y, cls, key, value):
    # HackGen Console NF は閲覧者の大半の環境に入っておらず、フォールバック
    # フォント(Menlo/Consolas等)では文字幅が変わるため、key部分をスペース
    # パディングして揃える方式だと列がズレる。key/valueそれぞれを固定x座標の
    # <tspan> に分けることで、フォントに関わらず値の開始位置を揃える。
    return (
        f'<text x="{x}" y="{y}" class="{cls}">'
        f'<tspan x="{x}">{esc(key)}</tspan>'
        f'<tspan x="{value_x}">{esc(value)}</tspan>'
        f'</text>'
    )


def status_class(status):
    return {
        "RUNNING": "green",
        "READING": "yellow",
        "PAUSED": "dim",
        "DONE": "accent",
    }.get(status.upper(), "mono")


def bar_seg_width(s):
    return round(len(s) * BAR_CHAR_W) + BAR_PAD * 2


def prompt_bar(y_top, path, branch, duration, time_display):
    """Starship の $directory -> $git_branch powerlineバー(右にduration/time)を描く．"""
    bar_bottom = y_top + BAR_H
    baseline = y_top + BAR_H / 2 + 3.2

    dir_text = f' {path} '
    git_text = f'  {GIT_BRANCH_ICON} {branch} '
    segments = [
        (dir_text, ACCENT, ON_ACCENT),
        (git_text, DARK, ACCENT),
    ]

    seg_x = LEFT
    rect_svg, seg_text_svg, arrow_svg, bounds = [], [], [], []
    for value, bg_color, fg_color in segments:
        w = bar_seg_width(value)
        rect_svg.append(f'<rect x="{seg_x}" y="{y_top}" width="{w}" height="{BAR_H}" fill="{bg_color}"/>')
        seg_text_svg.append(
            f'<text x="{seg_x + w/2}" y="{baseline}" class="barseg" '
            f'text-anchor="middle" fill="{fg_color}" font-weight="bold">{esc(value)}</text>'
        )
        bounds.append(seg_x + w)
        seg_x += w

    # powerline矢印: 各セグメント境界に、手前の色で右向き三角形を重ね描きする
    # (先に全セグメントのrectを描画してから矢印を上に重ねることで、次のセグメントに
    #  食い込む矢印が隠れずに見える)。最後の矢印はdark色のままプレーンな背景に抜ける。
    for boundary, (_, bg_color, _) in zip(bounds, segments):
        th = BAR_H / 2
        arrow_svg.append(
            f'<polygon points="{boundary},{y_top} {boundary+ARROW_W},{y_top+th} '
            f'{boundary},{bar_bottom}" fill="{bg_color}"/>'
        )

    svg = rect_svg + arrow_svg + seg_text_svg

    # right_format = "$cmd_duration$time" : 背景なしの装飾テキストとして右端に配置
    duration_text = f'{SEGMENT_ICON} {duration}'
    time_text = f'{SEGMENT_ICON} {time_display}'
    right_edge = WIDTH - LEFT
    time_w = bar_seg_width(time_text) + 8
    svg.append(f'<text x="{right_edge}" y="{baseline}" class="barright" text-anchor="end">{esc(time_text)}</text>')
    svg.append(
        f'<text x="{right_edge - time_w}" y="{baseline}" class="barright" '
        f'text-anchor="end">{esc(duration_text)}</text>'
    )
    return svg, bar_bottom


def prompt_and_command(block_svg, y_top, path, branch, duration, time_display, cmd, type_delay):
    """バー(パス/ブランチ) + 実行済みコマンド行 ($character 相当) を描き、
    コマンド行のbaseline(y)を返す。実機同様、コマンドを打つたびにバーが出る。
    コマンド文字列自体は type_delay 秒後にタイプ演出(clip-pathの左→右ワイプ)で
    出現させ、キーを打っている雰囲気を出す。"""
    bar_svg, bar_bottom = prompt_bar(y_top, path, branch, duration, time_display)
    block_svg.extend(bar_svg)
    cmd_y = bar_bottom + BAR_TO_CMD_GAP
    block_svg.append(
        f'<text x="{LEFT}" y="{cmd_y}" class="cmdline">'
        f'<tspan class="promptchar" font-weight="bold">&#10095;</tspan> '
        f'<tspan class="typeline" style="animation-delay:{type_delay:.2f}s">{esc(cmd)}</tspan>'
        f'</text>'
    )
    return cmd_y


with PROFILE_PATH.open(encoding="utf-8") as f:
    p = json.load(f)

identity = p["identity"]
systems = p.get("systems", {})
research = p.get("research", {})
projects = p.get("projects", [])
stack = p.get("stack", [])
prompt = p.get("prompt", {})

PATH = prompt.get("path", "")
BRANCH = prompt.get("branch", "")
DURATION = prompt.get("cmd_duration", "0s")
TIME_DISPLAY = prompt.get("time", "00:00")

# ブロック単位で貯めて、最後にまとめて <g class="reveal"> でラップする。
# (「タイピング再生」演出: ブロックが上から順に、少しずつ遅れて出現する)
blocks = []
current = []


def flush_block():
    global current
    if current:
        blocks.append(current)
        current = []


y = 74

current.append(text(LEFT, y, "title", f'{identity["username"]}@{identity["terminal_host"]}'))
y += 26
current.append(text(LEFT, y, "dim", "-" * 78))
flush_block()

WHOAMI_VALUE_X = LEFT + 96

y += CMD_TO_NEXT_BAR_GAP
delay = len(blocks) * BLOCK_DELAY_STEP
y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "whoami", delay + TYPE_DELAY_OFFSET)
for key, value in [
    ("Role", identity.get("role", "")),
    ("University", identity.get("university", "")),
    ("Lab", identity.get("lab", "")),
    ("Location", identity.get("location", "")),
]:
    y += 28 if key == "Role" else LINE_H
    current.append(kv_row(LEFT, WHOAMI_VALUE_X, y, "mono", key, value))
flush_block()

y += CMD_TO_NEXT_BAR_GAP
delay = len(blocks) * BLOCK_DELAY_STEP
y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "research --current", delay + TYPE_DELAY_OFFSET)
for item in research.get("current", []):
    y += LINE_H
    status = item.get("status", "").upper()
    label = item.get("label", "")
    current.append(text(LEFT, y, status_class(status), f"[{status}] {label}"))
flush_block()

description = research.get("description", [])
if description:
    y += CMD_TO_NEXT_BAR_GAP
    delay = len(blocks) * BLOCK_DELAY_STEP
    y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "cat research.txt", delay + TYPE_DELAY_OFFSET)
    for line in description:
        y += LINE_H
        current.append(text(LEFT, y, "mono", line))
    flush_block()

if stack:
    y += CMD_TO_NEXT_BAR_GAP
    delay = len(blocks) * BLOCK_DELAY_STEP
    y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "stack --list", delay + TYPE_DELAY_OFFSET)
    y += 28
    current.append(text(LEFT, y, "mono", " · ".join(stack)))
    flush_block()

ENV_VALUE_X = LEFT + 68

if systems:
    y += CMD_TO_NEXT_BAR_GAP
    delay = len(blocks) * BLOCK_DELAY_STEP
    y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "env --list", delay + TYPE_DELAY_OFFSET)
    y += 28
    current.append(kv_row(LEFT, ENV_VALUE_X, y, "mono", "OS", " · ".join(systems.get("os", []))))
    y += LINE_H
    current.append(kv_row(LEFT, ENV_VALUE_X, y, "mono", "Editor", systems.get("editor", "")))
    y += LINE_H
    current.append(kv_row(LEFT, ENV_VALUE_X, y, "mono", "WM", systems.get("wm", "")))
    flush_block()

PID_X = LEFT
NAME_X = LEFT + 42
STATUS_X = LEFT + 260

if projects:
    y += CMD_TO_NEXT_BAR_GAP
    delay = len(blocks) * BLOCK_DELAY_STEP
    y = prompt_and_command(current, y, PATH, BRANCH, DURATION, TIME_DISPLAY, "projects --active", delay + TYPE_DELAY_OFFSET)
    y += 28
    current.append(
        f'<text x="{PID_X}" y="{y}" class="dim">'
        f'<tspan x="{PID_X}">PID</tspan>'
        f'<tspan x="{NAME_X}">PROJECT</tspan>'
        f'<tspan x="{STATUS_X}">STATUS</tspan>'
        f'</text>'
    )
    for project in projects:
        y += LINE_H
        current.append(
            f'<text x="{PID_X}" y="{y}" class="mono">'
            f'<tspan x="{PID_X}">{esc(project.get("pid", ""))}</tspan>'
            f'<tspan x="{NAME_X}">{esc(project.get("name", ""))}</tspan>'
            f'<tspan x="{STATUS_X}">{esc(project.get("status", ""))}</tspan>'
            f'</text>'
        )
    flush_block()

body_bottom = y + 30

# --- 末尾: 次の入力を待つプロンプト (バー + 単独の $character、コマンドなし) ---
final_bar_svg, final_bar_bottom = prompt_bar(body_bottom, PATH, BRANCH, DURATION, TIME_DISPLAY)
current.extend(final_bar_svg)
character_baseline = final_bar_bottom + BAR_TO_CMD_GAP
current.append(
    f'<text x="{LEFT}" y="{character_baseline}" class="promptchar" font-weight="bold">&#10095;</text>'
)
current.append(
    f'<rect x="{LEFT + 14}" y="{character_baseline - 11}" width="6" height="13" rx="1" class="cursor"/>'
)
flush_block()

height = character_baseline + 20

# ブロックを <g class="reveal"> でラップし、出現順に少しずつ遅延させる
reveal_svg = []
for i, block in enumerate(blocks):
    d = i * BLOCK_DELAY_STEP
    reveal_svg.append(f'<g class="reveal" style="animation-delay:{d:.2f}s">{"".join(block)}</g>')

# --- タブバー (信号ボタン行 + タブ行の2段構成) ---
DOT_ROW_H = 30
TAB_ROW_H = 26
HEADER_H = DOT_ROW_H + TAB_ROW_H
tab_label = "zsh"
tab_w = round(len(tab_label) * 7.2) + 14
tab_x = 16
tab_skew = 7

svg = f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <pattern id="scanlines" width="100%" height="4" patternUnits="userSpaceOnUse">
      <rect width="100%" height="2" fill="#000000" opacity="0.35"/>
    </pattern>
    <radialGradient id="vignette" cx="50%" cy="42%" r="75%">
      <stop offset="60%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.35"/>
    </radialGradient>
  </defs>
  <style>
    text {{ font-family: {FONT}; }}
    .bg {{ fill: {BG}; }}
    .border {{ stroke: {BORDER}; stroke-width: 1.5; }}
    .mono {{ font-size: 14px; fill: {FG}; }}
    .title {{ font-size: 16px; font-weight: 700; fill: {ACCENT}; }}
    .cmdline {{ font-size: 14px; fill: {FG}; }}
    .promptchar {{ fill: {SECONDARY}; font-size: 14px; }}
    .dim {{ font-size: 14px; fill: {DIM}; }}
    .green {{ font-size: 14px; fill: {DRAGON_GREEN}; }}
    .yellow {{ font-size: 14px; fill: {DRAGON_YELLOW}; }}
    .accent {{ font-size: 14px; fill: {ACCENT}; }}
    .tabtext {{ font-size: 12px; fill: {ON_ACCENT}; font-weight: 700; }}
    .barseg {{ font-size: {BAR_FONT}px; }}
    .barright {{ font-size: {BAR_FONT}px; font-weight: 700; fill: {MUTED}; }}
    .cursor {{ fill: {CARET}; animation: blink 1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}

    /* タイピング再生 (1回完結): ブロックが上からフェード+スライドインで
       順番に出現する。librsvg等の静的レンダラやreduced-motion環境は
       @media を解釈できず/評価がfalseになり、下の「常に表示」がそのまま
       効くようフォールバックにしている (これが無いと、アニメーション未再生の
       環境で opacity:0 のまま止まって真っ黒に見えてしまう)。 */
    .reveal {{ opacity: 1; }}
    .typeline {{ display: inline-block; clip-path: inset(0 0 0 0); }}
    @media (prefers-reduced-motion: no-preference) {{
      .reveal {{
        opacity: 0;
        transform: translateY(5px);
        animation: revealIn 0.5s ease-out both;
      }}
      /* コマンド文字列だけ、バーの出現から少し遅れて左→右にタイプされる演出 */
      .typeline {{
        clip-path: inset(0 100% 0 0);
        animation: typeReveal 0.5s steps(18, end) both;
      }}
    }}
    @keyframes revealIn {{
      from {{ opacity: 0; transform: translateY(5px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes typeReveal {{
      to {{ clip-path: inset(0 0 0 0); }}
    }}

    /* 常時ループするスキャンライン(CRT風の走査線) */
    .scanlines {{
      mix-blend-mode: overlay;
      animation: scanmove 5s linear infinite;
    }}
    @keyframes scanmove {{
      from {{ transform: translateY(0); }}
      to   {{ transform: translateY(4px); }}
    }}
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

  {"".join(reveal_svg)}

  <rect x="0.75" y="{HEADER_H}" width="{WIDTH-1.5}" height="{height-HEADER_H-0.75}" fill="url(#scanlines)" class="scanlines" pointer-events="none"/>
  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" fill="url(#vignette)" pointer-events="none"/>
</svg>
"""

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(svg, encoding="utf-8")
print(f"Generated {OUTPUT_PATH}")
