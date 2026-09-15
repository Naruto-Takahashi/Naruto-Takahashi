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
INACTIVE_TAB_BG = "#3a3a3a"  # 濃い灰色 (非アクティブタブ)
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
# 実機では各コマンド実行のたびにこのプロンプトブロックが表示される
# (1回だけ末尾に出るのではない) ため、コマンド行ごとに描画する。
# right_format の $cmd_duration$time は表示が細かすぎて情報量に見合わない
# ノイズだったため廃止し、directory/git_branchのバーだけに絞った。
# git_branch のアイコンは以前 Nerd Font の PUA コードポイント(U+F418)を
# 使っていたが、そのフォントを持たない閲覧者のブラウザではグリフが
# 表示されず消えて見える問題があったため、フォント非依存のベクターpathで
# 小さな branch アイコンを直接描く方式にしている。

# バー自体は実機のように細く (フォントサイズ・パディングを本文より一段階小さく)
BAR_H = 15
BAR_FONT = 10
BAR_CHAR_W = 5.1
BAR_PAD = 3
ARROW_W = 6
BAR_TO_CMD_GAP = 22
CMD_TO_NEXT_BAR_GAP = 30
GIT_ICON_W = 26  # branchアイコン用に確保する幅 (powerline矢印の食い込み分+左余白+アイコン本体+余白)

# タイピング再生のタイムライン制御:
#   バー出現 -> (TYPE_DELAY_OFFSET後) タイプ開始 -> 打ち終わり
#   -> (ENTER_PAUSE後、Enterを押したイメージ) 出力がフェードイン
#   -> (OUTPUT_REVEAL_DUR+POST_GAP後) 次のコマンドのバーが出現
# の順を守ることで、「打ち終わる前に結果が出る」不自然さを無くしている。
TYPE_DELAY_OFFSET = 0.12
ENTER_PAUSE = 0.15
OUTPUT_REVEAL_DUR = 0.5
POST_GAP = 0.3


def type_duration(cmd):
    # コマンド文字列が長いほど打つのに時間がかかるようにし、全コマンドが
    # 同じ速度で一律に打たれる不自然さ(等速タイピング)を避ける。
    return round(0.5 + len(cmd) * 0.045, 2)


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


def git_branch_icon_svg(cx, cy, color):
    """Nerd Fontのグリフに頼らず、フォーク型の小さなgit branchアイコンを
    ベクターpathで直接描く(閲覧者の環境を問わず必ず表示される)。"""
    r = 1.5
    top = (cx - 3, cy - 4.5)
    bottom = (cx - 3, cy + 4.5)
    branch = (cx + 3, cy - 2.5)
    return (
        f'<g stroke="{color}" stroke-width="1.3" fill="none" stroke-linecap="round">'
        f'<line x1="{top[0]}" y1="{top[1]+r}" x2="{bottom[0]}" y2="{bottom[1]-r}"/>'
        f'<path d="M {top[0]} {cy-0.5} C {top[0]+2.5} {cy-0.5} {branch[0]-2.5} {branch[1]} {branch[0]} {branch[1]}"/>'
        f'</g>'
        f'<circle cx="{top[0]}" cy="{top[1]}" r="{r}" fill="{color}"/>'
        f'<circle cx="{bottom[0]}" cy="{bottom[1]}" r="{r}" fill="{color}"/>'
        f'<circle cx="{branch[0]}" cy="{branch[1]}" r="{r}" fill="{color}"/>'
    )


def prompt_bar(y_top, path, branch):
    """Starship の $directory -> $git_branch powerlineバーを描く。"""
    bar_bottom = y_top + BAR_H
    baseline = y_top + BAR_H / 2 + 3.2
    icon_cy = y_top + BAR_H / 2

    dir_text = f' {path} '
    dir_w = bar_seg_width(dir_text)

    branch_label = f' {branch} '
    branch_label_w = bar_seg_width(branch_label)
    git_w = GIT_ICON_W + branch_label_w

    segments_geometry = [
        (LEFT, dir_w),
        (LEFT + dir_w, git_w),
    ]

    rect_svg = [
        f'<rect x="{LEFT}" y="{y_top}" width="{dir_w}" height="{BAR_H}" fill="{ACCENT}"/>',
        f'<rect x="{LEFT + dir_w}" y="{y_top}" width="{git_w}" height="{BAR_H}" fill="{DARK}"/>',
    ]

    dir_text_svg = (
        f'<text x="{LEFT + dir_w/2}" y="{baseline}" class="barseg" '
        f'text-anchor="middle" fill="{ON_ACCENT}" font-weight="bold">{esc(dir_text)}</text>'
    )

    git_seg_x = LEFT + dir_w
    # powerline矢印(ARROW_W幅、accent色)がgitセグメントの左端に食い込んでいるため、
    # アイコンをaccent色そのままで置くとそこに埋もれて見えなくなる。矢印の外側
    # (dark背景の上)まで押し出して配置する。
    icon_cx = git_seg_x + ARROW_W + BAR_PAD + 6
    icon_svg = git_branch_icon_svg(icon_cx, icon_cy, ACCENT)
    branch_text_svg = (
        f'<text x="{git_seg_x + GIT_ICON_W}" y="{baseline}" class="barseg" '
        f'fill="{ACCENT}" font-weight="bold">{esc(branch_label)}</text>'
    )

    # powerline矢印: 各セグメント境界に、手前の色で右向き三角形を重ね描きする
    # (先に全セグメントのrectを描画してから矢印を上に重ねることで、次のセグメントに
    #  食い込む矢印が隠れずに見える)。最後の矢印はdark色のままプレーンな背景に抜ける。
    arrow_svg = []
    for x, w in segments_geometry:
        boundary = x + w
        bg_color = ACCENT if x == LEFT else DARK
        th = BAR_H / 2
        arrow_svg.append(
            f'<polygon points="{boundary},{y_top} {boundary+ARROW_W},{y_top+th} '
            f'{boundary},{bar_bottom}" fill="{bg_color}"/>'
        )

    svg = rect_svg + arrow_svg + [dir_text_svg, icon_svg, branch_text_svg]
    return svg, bar_bottom


def prompt_and_command(block_svg, y_top, path, branch, cmd, type_delay, variant=0):
    """バー(パス/ブランチ) + 実行済みコマンド行 ($character 相当) を描き、
    コマンド行のbaseline(y)を返す。実機同様、コマンドを打つたびにバーが出る。
    コマンド文字列自体は type_delay 秒後にタイプ演出(clip-pathの左→右ワイプ)で
    出現させ、キーを打っている雰囲気を出す。打鍵速度が一律だと不自然なため、
    文字数に応じた長さ(type_duration)と、2種類の緩急パターン(variant)を
    交互に割り当てて速度にばらつきを持たせている。"""
    bar_svg, bar_bottom = prompt_bar(y_top, path, branch)
    block_svg.extend(bar_svg)
    cmd_y = bar_bottom + BAR_TO_CMD_GAP
    dur = type_duration(cmd)
    variant_cls = "typeline" if variant == 0 else "typeline typeline-b"
    block_svg.append(
        f'<text x="{LEFT}" y="{cmd_y}" class="cmdline">'
        f'<tspan class="promptchar" font-weight="bold">&#10095;</tspan> '
        f'<tspan class="{variant_cls}" '
        f'style="animation-delay:{type_delay:.2f}s;animation-duration:{dur:.2f}s">{esc(cmd)}</tspan>'
        f'</text>'
    )
    return cmd_y, dur


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

# ブロック単位で貯めて、最後にまとめて <g class="reveal"> でラップする。
# (「タイピング再生」演出: ブロックが上から順に、少しずつ遅れて出現する)
# block_delaysは各ブロックの出現ディレイを対応するindexで保持する。
blocks = []
block_delays = []
current = []
pending_delay = 0.0


def flush_block():
    global current
    if current:
        blocks.append(current)
        block_delays.append(pending_delay)
        current = []


y = 64

current.append(text(LEFT, y, "title", f'{identity["username"]}@{identity["terminal_host"]}'))
y += 26
current.append(text(LEFT, y, "dim", "-" * 78))
flush_block()

# タイムライン: バー出現 -> タイプ -> (Enter想定のポーズ) -> 出力フェードイン
# -> 次のバー、の順で経過時間を積み上げていく。バー+コマンド行はその場で
# 独立したブロックとして即座にflushし、出力側は呼び出し元がoutput_delayを
# 使って別ブロックとして後からflushすることで、「打ち終わる前に結果が
# 表示される」不自然さを避けている。
total_delay = 0.4
variant = 0
output_delay = 0.0


def run_command(y, cmd):
    global total_delay, variant, output_delay
    d_bar = total_delay
    cmd_block = []
    cmd_y, dur = prompt_and_command(cmd_block, y, PATH, BRANCH, cmd, d_bar + TYPE_DELAY_OFFSET, variant)
    blocks.append(cmd_block)
    block_delays.append(d_bar)

    output_delay = d_bar + TYPE_DELAY_OFFSET + dur + ENTER_PAUSE
    total_delay = output_delay + OUTPUT_REVEAL_DUR + POST_GAP
    variant = 1 - variant
    return cmd_y


WHOAMI_VALUE_X = LEFT + 96

y += CMD_TO_NEXT_BAR_GAP
y = run_command(y, "whoami")
pending_delay = output_delay
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
y = run_command(y, "research --current")
pending_delay = output_delay
for item in research.get("current", []):
    y += LINE_H
    status = item.get("status", "").upper()
    label = item.get("label", "")
    current.append(text(LEFT, y, status_class(status), f"[{status}] {label}"))
flush_block()

description = research.get("description", [])
if description:
    y += CMD_TO_NEXT_BAR_GAP
    y = run_command(y, "cat research.txt")
    pending_delay = output_delay
    for line in description:
        y += LINE_H
        current.append(text(LEFT, y, "mono", line))
    flush_block()

if stack:
    y += CMD_TO_NEXT_BAR_GAP
    y = run_command(y, "stack --list")
    pending_delay = output_delay
    y += 28
    current.append(text(LEFT, y, "mono", " · ".join(stack)))
    flush_block()

ENV_VALUE_X = LEFT + 68

if systems:
    y += CMD_TO_NEXT_BAR_GAP
    y = run_command(y, "env --list")
    pending_delay = output_delay
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
    y = run_command(y, "projects --active")
    pending_delay = output_delay
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
pending_delay = total_delay
final_bar_svg, final_bar_bottom = prompt_bar(body_bottom, PATH, BRANCH)
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
for block, d in zip(blocks, block_delays):
    reveal_svg.append(f'<g class="reveal" style="animation-delay:{d:.2f}s">{"".join(block)}</g>')

# --- タブバー (信号ボタン行 + タブ行の2段構成)。上下方向の厚みを薄くしている ---
DOT_ROW_H = 20
TAB_ROW_H = 18
HEADER_H = DOT_ROW_H + TAB_ROW_H
tab_skew = 6
TAB_GAP = 3

# アクティブタブは「今まさにこのprofile.jsonを覗いている」というメタな
# ネタとして、シェル名ではなくデータソースのファイル名を表示する。
# 隣には実際の開発環境(Neovim + WezTerm)を匂わせる非アクティブなタブを
# 並べ、普段づかいの多タブ構成っぽい雰囲気を出している。
active_tab_label = "profile"
inactive_tab_labels = ["nvim", "lazygit"]


def tab_polygon(x, w, y_top, y_bottom, skew):
    return f'{x},{y_top} {x+skew},{y_bottom} {x+w+skew},{y_bottom} {x+w},{y_top}'


tab_svg = []
tab_x = 16
active_w = round(len(active_tab_label) * 7.2) + 14
tab_svg.append(
    f'<polygon points="{tab_polygon(tab_x, active_w, DOT_ROW_H, HEADER_H, tab_skew)}" fill="{ACCENT}"/>'
)
tab_svg.append(text(tab_x + active_w/2 + tab_skew/2, DOT_ROW_H + TAB_ROW_H*0.68, "tabtext", active_tab_label, anchor="middle"))
tab_x += active_w + tab_skew + TAB_GAP

for label in inactive_tab_labels:
    w = round(len(label) * 6.6) + 12
    tab_svg.append(
        f'<polygon points="{tab_polygon(tab_x, w, DOT_ROW_H, HEADER_H, tab_skew)}" '
        f'fill="{INACTIVE_TAB_BG}"/>'
    )
    tab_svg.append(text(tab_x + w/2 + tab_skew/2, DOT_ROW_H + TAB_ROW_H*0.68, "tabtext-inactive", label, anchor="middle"))
    tab_x += w + tab_skew + TAB_GAP

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
    .tabtext-inactive {{ font-size: 12px; fill: #ffffff; font-weight: 700; }}
    .barseg {{ font-size: {BAR_FONT}px; }}
    .cursor {{ fill: {CARET}; animation: blink 1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}

    /* タイピング再生 (1回完結): ブロックが上からフェード+スライドインで
       順番に出現する。prefers-reduced-motionでは分岐させない
       (Vivaldi等、OS側の「モーションを減らす」設定が意図せずオンになっていると
       それだけでアニメーションが再生されなくなってしまうため、常に再生する)。
       その代わり、静的なopacity/clip-pathの宣言としては「常にフル表示」
       (opacity:1 / clip-path:フル開放) だけを書き、非表示状態は
       @keyframesの0%側にしか存在しないようにしている。こうすることで
       librsvg等アニメーションを実行できないレンダラは単に静的な
       opacity:1をそのまま使い、対応ブラウザだけがアニメーション通りに
       0%から再生する(=静的レンダラでも真っ黒にならない)。 */
    .reveal {{
      opacity: 1;
      animation: revealIn 0.5s ease-out both;
    }}
    /* コマンド文字列だけ、バーの出現から少し遅れて左→右にタイプされる演出。
       等速だと不自然なので、バーストと一瞬の"打鍵の迷い"を混ぜた不均一な
       キーフレームにし、animation-durationは文字数で個別に伸縮させている
       (prompt_and_command/type_duration参照)。2種類のカーブ(typeline-b)を
       コマンドごとに交互適用し、毎回同じリズムに見えないようにした。 */
    .typeline {{
      display: inline-block;
      clip-path: inset(0 0 0 0);
      animation-name: typeReveal;
      animation-timing-function: linear;
      animation-fill-mode: both;
    }}
    .typeline-b {{ animation-name: typeReveal2; }}
    @keyframes revealIn {{
      from {{ opacity: 0; transform: translateY(5px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    /* 序盤は勢いよく、途中で一瞬迷って止まり、後半また打ち切る緩急 */
    @keyframes typeReveal {{
      0%   {{ clip-path: inset(0 100% 0 0); }}
      22%  {{ clip-path: inset(0 74% 0 0); }}
      30%  {{ clip-path: inset(0 71% 0 0); }}
      46%  {{ clip-path: inset(0 46% 0 0); }}
      52%  {{ clip-path: inset(0 44% 0 0); }}
      74%  {{ clip-path: inset(0 16% 0 0); }}
      100% {{ clip-path: inset(0 0% 0 0); }}
    }}
    /* variant B: 迷いのタイミングをずらした別カーブ */
    @keyframes typeReveal2 {{
      0%   {{ clip-path: inset(0 100% 0 0); }}
      12%  {{ clip-path: inset(0 88% 0 0); }}
      34%  {{ clip-path: inset(0 58% 0 0); }}
      40%  {{ clip-path: inset(0 56% 0 0); }}
      62%  {{ clip-path: inset(0 30% 0 0); }}
      68%  {{ clip-path: inset(0 28% 0 0); }}
      100% {{ clip-path: inset(0 0% 0 0); }}
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

  <circle cx="22" cy="{DOT_ROW_H/2}" r="4.5" fill="{DRAGON_RED}"/>
  <circle cx="39" cy="{DOT_ROW_H/2}" r="4.5" fill="{DRAGON_YELLOW}"/>
  <circle cx="56" cy="{DOT_ROW_H/2}" r="4.5" fill="{DRAGON_GREEN}"/>

  {"".join(tab_svg)}

  {"".join(reveal_svg)}

  <rect x="0.75" y="{HEADER_H}" width="{WIDTH-1.5}" height="{height-HEADER_H-0.75}" fill="url(#scanlines)" class="scanlines" pointer-events="none"/>
  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" fill="url(#vignette)" pointer-events="none"/>
</svg>
"""

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(svg, encoding="utf-8")
print(f"Generated {OUTPUT_PATH}")
