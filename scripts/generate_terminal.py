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
OUTPUT_PATH = ROOT / "assets" / "profile.svg"

WIDTH = 820
LEFT = 32
LINE_H = 26

FONT = ('"HackGen Console NF", "SFMono-Regular", "Cascadia Code", '
        '"Roboto Mono", Menlo, Consolas, monospace')

# Kanagawa Dragon (実測値: kanagawa-dragon.tmTheme)
BG = "#181616"
BG_ALT = "#1d1c19"      # タブバー相当 (bg寄りの濃色)
FG = "#c5c9c5"
DIM = "#737c73"         # コメント色
BORDER = "#282727"
DRAGON_GREEN = "#87a987"
DRAGON_YELLOW = "#c4b28a"
DRAGON_RED = "#c4746e"

# kanagawa-dragon.tmTheme のシンタックスハイライト配色 (実測値)。
# ターミナル全体を塗り分けるのではなく、実際にコードを読む時の役割
# (関数名/キーワード/型名/文字列) に近い意味を持つ場所だけに絞って使う。
DRAGON_STRING = "#8a9a7b"   # scope: string
DRAGON_STORAGE = "#8992a7"  # scope: storage, storage.type (キーワード/フラグ相当)
DRAGON_FUNC = "#8ba4b0"     # scope: entity.name.function (コマンド名相当)
DRAGON_CLASS = "#8ea4a2"    # scope: entity.name.class (プロジェクト名相当)
DRAGON_CONST = "#b6927b"    # scope: constant.language

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
BAR_H = 18
BAR_FONT = 11
BAR_CHAR_W = 5.6
BAR_PAD = 4
ARROW_W = 6
BAR_TO_CMD_GAP = 24
CMD_TO_NEXT_BAR_GAP = 30
GIT_ICON_W = 29  # branchアイコン用に確保する幅 (powerline矢印の食い込み分+左余白+アイコン本体+余白)

# タイピング再生のタイムライン制御 (テンポ良くシャープに表示)
TYPE_DELAY_OFFSET = 0.06
ENTER_PAUSE = 0.08
OUTPUT_REVEAL_DUR = 0.25
POST_GAP = 0.14


def type_duration(cmd):
    return round(0.24 + len(cmd) * 0.022, 2)


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
        f'<tspan x="{x}" class="syn-storage">{esc(key)}</tspan>'
        f'<tspan x="{value_x}">{esc(value)}</tspan>'
        f'</text>'
    )


# HackGen Console NF を持たない環境(特にスマホのブラウザ)では、フォールバック
# monospaceフォントの字幅がPCより広くなる。列を固定pxで並べる箇所はどこでも
# 同じ問題(長い項目が次列に食い込んで見える)が起き得るため、実際の内容の
# 最大文字数から必要幅を逆算する column_x() に一本化する。
SAFE_CHAR_W = 10.8  # 16pxフォントでフォールバック時も重ならない安全側の1文字幅(px)
COL_GAP = 20        # 列間の最低余白(px)


def column_x(start_x, *col_samples):
    """各列の開始x座標を、直前列の内容の最大文字数から計算して返す。
    col_samples には2列目以降それぞれについて、その列の「直前」に来る列の
    セル文字列(ヘッダも含めてよい)のリストを渡す。返り値の長さは
    len(col_samples) + 1 (先頭は常に start_x)。"""
    xs = [start_x]
    x = start_x
    for samples in col_samples:
        max_len = max((len(s) for s in samples), default=0)
        x += round(max_len * SAFE_CHAR_W) + COL_GAP
        xs.append(x)
    return xs


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
    icon_cx = git_seg_x + ARROW_W + BAR_PAD + 9
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
        f'style="animation-delay:{type_delay:.2f}s;animation-duration:{dur:.2f}s">{highlight_cmd(cmd)}</tspan>'
        f'</text>'
    )
    return cmd_y, dur


def highlight_cmd(cmd):
    """コマンド行を最小限だけシンタックスハイライトする:
    先頭のコマンド名は Function name 色、--flag は Storage(キーワード)色、
    残りは通常の前景色のまま。"""
    parts = cmd.split(" ")
    out = []
    for i, part in enumerate(parts):
        if i == 0:
            cls = "syn-func"
        elif part.startswith("--"):
            cls = "syn-storage"
        else:
            cls = None
        token = esc(part)
        out.append(f'<tspan class="{cls}">{token}</tspan>' if cls else token)
        if i != len(parts) - 1:
            out.append(" ")
    return "".join(out)


with PROFILE_PATH.open(encoding="utf-8") as f:
    p = json.load(f)

identity = p["identity"]
systems = p.get("systems", {})
research = p.get("research", {})
projects = p.get("projects", [])
stack = p.get("stack", {})
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


HEADER_H = 26
y = HEADER_H + 22

# タイムライン: バー出現 -> タイプ -> (Enter想定のポーズ) -> 出力フェードイン
# -> 次のバー、の順で経過時間を積み上げていく。
total_delay = 0.25
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


y = run_command(y, "whoami")
pending_delay = output_delay
whoami_rows = [
    ("Role", identity.get("role", "")),
    ("Affiliation", identity.get("affiliation", "")),
    ("Interests", identity.get("interests", "")),
]
KEY_X, VALUE_X = column_x(LEFT, [key for key, _ in whoami_rows])
for key, value in whoami_rows:
    y += 28 if key == "Role" else LINE_H
    current.append(kv_row(KEY_X, VALUE_X, y, "mono", key, value))
flush_block()

focus_items = p.get("focus", [])
if focus_items:
    TAG_X, LABEL_X = column_x(LEFT, [f"[{it.get('tag', '')}]" for it in focus_items])
    tag_colors = {"RESEARCH": "green", "SOLVE": "yellow", "DEV": "accent"}
    y += CMD_TO_NEXT_BAR_GAP
    y = run_command(y, "focus --active")
    pending_delay = output_delay
    for i, item in enumerate(focus_items):
        y += 28 if i == 0 else LINE_H
        tag = item.get("tag", "").upper()
        label = item.get("label", "")
        cls = tag_colors.get(tag, "accent")
        current.append(
            f'<text x="{TAG_X}" y="{y}" class="mono">'
            f'<tspan x="{TAG_X}" class="{cls}">[{esc(tag)}]</tspan>'
            f'<tspan x="{LABEL_X}">{esc(label)}</tspan>'
            f'</text>'
        )
    flush_block()

if stack:
    y += CMD_TO_NEXT_BAR_GAP
    y = run_command(y, "stack --core")
    pending_delay = output_delay
    y += 28
    lang_colors = ["syn-func", "syn-storage", "syn-class", "syn-const"]
    lang_spans = []
    for i, lang in enumerate(stack.get("languages", [])):
        if i:
            lang_spans.append('<tspan class="dim"> · </tspan>')
        lang_spans.append(f'<tspan class="{lang_colors[i % len(lang_colors)]}">{esc(lang)}</tspan>')
    current.append(f'<text x="{LEFT}" y="{y}" class="mono">{"".join(lang_spans)}</text>')
    flush_block()

body_bottom = y + 26

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

svg = f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="vignette" cx="50%" cy="42%" r="75%">
      <stop offset="65%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.22"/>
    </radialGradient>
  </defs>
  <style>
    text {{ font-family: {FONT}; }}
    .bg {{ fill: {BG}; }}
    .border {{ stroke: {BORDER}; stroke-width: 1.5; }}
    .mono {{ font-size: 16px; fill: {FG}; }}
    .title {{ font-size: 16px; font-weight: 700; fill: {TERTIARY}; }}
    .cmdline {{ font-size: 16px; fill: {FG}; }}
    .promptchar {{ fill: {SECONDARY}; font-size: 16px; }}
    .dim {{ font-size: 16px; fill: {DIM}; }}
    .green {{ font-size: 16px; fill: {DRAGON_GREEN}; }}
    .yellow {{ font-size: 16px; fill: {DRAGON_YELLOW}; }}
    .accent {{ font-size: 16px; fill: {ACCENT}; }}
    .syn-func {{ fill: {DRAGON_FUNC}; }}
    .syn-storage {{ fill: {DRAGON_STORAGE}; }}
    .syn-class {{ fill: {DRAGON_CLASS}; }}
    .syn-string {{ fill: {DRAGON_STRING}; }}
    .syn-const {{ fill: {DRAGON_CONST}; }}
    .barseg {{ font-size: {BAR_FONT}px; }}
    .cursor {{ fill: {TERTIARY}; animation: blink 1s steps(2, start) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}

    .reveal {{
      opacity: 1;
      animation: revealIn 0.25s ease-out both;
    }}
    .typeline {{
      display: inline-block;
      clip-path: inset(0 0 0 0);
      animation-name: typeReveal;
      animation-timing-function: linear;
      animation-fill-mode: both;
    }}
    .typeline-b {{ animation-name: typeReveal2; }}
    @keyframes revealIn {{
      from {{ opacity: 0; transform: translateY(2px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes typeReveal {{
      0%   {{ clip-path: inset(0 100% 0 0); }}
      22%  {{ clip-path: inset(0 74% 0 0); }}
      30%  {{ clip-path: inset(0 71% 0 0); }}
      46%  {{ clip-path: inset(0 46% 0 0); }}
      52%  {{ clip-path: inset(0 44% 0 0); }}
      74%  {{ clip-path: inset(0 16% 0 0); }}
      100% {{ clip-path: inset(0 0% 0 0); }}
    }}
    @keyframes typeReveal2 {{
      0%   {{ clip-path: inset(0 100% 0 0); }}
      12%  {{ clip-path: inset(0 88% 0 0); }}
      34%  {{ clip-path: inset(0 58% 0 0); }}
      40%  {{ clip-path: inset(0 56% 0 0); }}
      62%  {{ clip-path: inset(0 30% 0 0); }}
      68%  {{ clip-path: inset(0 28% 0 0); }}
      100% {{ clip-path: inset(0 0% 0 0); }}
    }}
  </style>

  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" class="bg border"/>

  <path d="M 0.75 12.75 Q 0.75 0.75 12.75 0.75 L {WIDTH-12.75} 0.75 Q {WIDTH-0.75} 0.75 {WIDTH-0.75} 12.75
           L {WIDTH-0.75} {HEADER_H} L 0.75 {HEADER_H} Z" fill="{BG_ALT}"/>
  <line x1="0.75" y1="{HEADER_H}" x2="{WIDTH-0.75}" y2="{HEADER_H}" stroke="{BORDER}" stroke-width="1"/>

  <circle cx="22" cy="{HEADER_H/2}" r="4.5" fill="{DRAGON_RED}"/>
  <circle cx="39" cy="{HEADER_H/2}" r="4.5" fill="{DRAGON_YELLOW}"/>
  <circle cx="56" cy="{HEADER_H/2}" r="4.5" fill="{DRAGON_GREEN}"/>

  {"".join(reveal_svg)}

  <rect x="0.75" y="0.75" width="{WIDTH-1.5}" height="{height-1.5}" rx="12" fill="url(#vignette)" pointer-events="none"/>
</svg>
"""

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(svg, encoding="utf-8")
print(f"Generated {OUTPUT_PATH}")
