"""Visual identity of the dashboard: an airline 'control tower / departure board' theme.

Contains the palette, global CSS and small HTML component helpers (boarding-pass KPI cards,
departure-board tables, pilot-note call-outs). No data logic lives here.
"""
from __future__ import annotations

import html
from typing import Iterable, Sequence

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------------------------------- palette
NAVY = "#0B1F3A"
SKY = "#1E88E5"
SKY_LIGHT = "#8EC5FC"
CLOUD = "#F3F8FD"
AMBER = "#FFB300"      # departure-board amber
ALERT = "#E4572E"      # delay / cancellation red-orange
GOOD = "#1FA77A"       # on-time green
TEAL = "#00A6A6"
PURPLE = "#7B5EA7"
COLORWAY = [SKY, ALERT, AMBER, TEAL, PURPLE, NAVY, "#F78FB3", "#6C8EAD"]
CAUSE_COLORS = {"Carrier": SKY, "Weather": TEAL, "NAS": AMBER, "Security": "#9AA5B1", "Late Aircraft": ALERT}

# --------------------------------------------------------------------------- plotly template
pio.templates["airline"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, Segoe UI, sans-serif", color=NAVY, size=13),
        colorway=COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(font=dict(family="Outfit, Inter, sans-serif", size=17, color=NAVY), x=0.01),
        xaxis=dict(gridcolor="#E3ECF5", zerolinecolor="#CFDCEB", linecolor="#CFDCEB"),
        yaxis=dict(gridcolor="#E3ECF5", zerolinecolor="#CFDCEB", linecolor="#CFDCEB"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=50, t=85, b=10),
        hoverlabel=dict(bgcolor=NAVY, font_color="white"),
    )
)
pio.templates.default = "airline"


def style(fig: go.Figure, title: str | None = None, height: int = 420) -> go.Figure:
    """Apply the shared look to a figure."""
    fig.update_layout(template="airline", height=height)
    if title:
        fig.update_layout(title_text=title)
    return fig


# --------------------------------------------------------------------------- CSS
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700&family=Inter:wght@400;500;600&family=Share+Tech+Mono&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
.stApp {{ background: linear-gradient(180deg, #E4F0FB 0%, {CLOUD} 320px, {CLOUD} 100%); }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 3.6rem; padding-bottom: 3rem; max-width: 1400px; }}

/* ---------- hero ---------- */
.hero {{
  position: relative; overflow: hidden; border-radius: 22px; padding: 28px 34px; margin-bottom: 18px;
  background: linear-gradient(120deg, {NAVY} 0%, #123A6B 55%, {SKY} 100%); color: white;
  box-shadow: 0 10px 30px rgba(11,31,58,.25);
}}
.hero h1 {{ font-family: 'Outfit', sans-serif; font-size: 2.1rem; margin: 0 0 4px 0; letter-spacing: .3px; color: white; }}
.hero p {{ margin: 0; color: #CFE3F7; font-size: .98rem; }}
.hero .tag {{ display:inline-block; font-family:'Share Tech Mono',monospace; background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.25); border-radius: 999px; padding: 3px 12px; margin: 10px 8px 0 0; font-size: .82rem; }}
.hero .plane {{ position:absolute; right:38px; top:14px; font-size: 4.2rem; opacity:.9; transform: rotate(-8deg); }}
.hero .trail {{ position:absolute; right:0; bottom:20px; width:55%; border-top: 2px dashed rgba(255,255,255,.35); }}
.hero .cloud {{ position:absolute; font-size:2.6rem; opacity:.18; }}

/* ---------- boarding-pass KPI card ---------- */
.pass {{
  position: relative; background: white; border-radius: 16px; padding: 14px 30px 12px 18px; min-height: 128px;
  box-shadow: 0 4px 16px rgba(11,31,58,.08); border-left: 6px solid var(--accent, {SKY}); overflow: hidden;
}}
.pass::after {{ content:""; position:absolute; right:14px; top:10px; bottom:10px; border-right: 2px dashed #D6E4F2; }}
.pass::before {{ content:""; position:absolute; right:7px; top:-8px; width:16px; height:16px; background:{CLOUD}; border-radius:50%; }}
.pass .lbl {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:.68rem; letter-spacing:.09em; text-transform:uppercase; color:#6B7C93; font-weight:600; }}
.pass .val {{ font-family:'Outfit',sans-serif; font-size:1.6rem; font-weight:700; color:{NAVY}; line-height:1.15; margin-top:2px; white-space:nowrap; }}
.pass .val.sm {{ font-size:1.12rem; white-space:normal; }}
.pass .sub {{ font-size:.74rem; color:#6B7C93; margin-top:3px; line-height:1.3; }}
.pass .delta-good {{ color:{GOOD}; font-weight:600; }} .pass .delta-bad {{ color:{ALERT}; font-weight:600; }}
.pass .delta-flat {{ color:#6B7C93; font-weight:600; }}

/* ---------- section titles ---------- */
.sec {{ font-family:'Outfit',sans-serif; font-size:1.25rem; font-weight:600; color:{NAVY}; margin: 22px 0 8px 0; }}
.sec::after {{ content:""; display:block; margin-top:6px; height:3px; width:100%;
  background: repeating-linear-gradient(90deg, {SKY} 0 22px, transparent 22px 34px); border-radius:2px; opacity:.55; }}

/* ---------- pilot note ---------- */
.note {{ background: white; border-radius: 14px; border-left: 5px solid {AMBER}; padding: 12px 16px; margin: 8px 0 14px 0;
  box-shadow: 0 3px 12px rgba(11,31,58,.06); font-size: .93rem; }}
.note b.k {{ font-family:'Outfit',sans-serif; color:{NAVY}; }}
.note.sky {{ border-left-color: {SKY}; }} .note.red {{ border-left-color: {ALERT}; }}

/* ---------- departure board ---------- */
.board {{ background:#07101F; border-radius:14px; padding: 10px 14px 12px 14px; box-shadow: 0 6px 20px rgba(0,0,0,.25); overflow-x:auto; }}
.board .cap {{ font-family:'Share Tech Mono',monospace; color:#8FA3BF; font-size:.78rem; letter-spacing:.16em; margin:2px 0 8px 2px; }}
.board table {{ width:100%; border-collapse: collapse; font-family:'Share Tech Mono', monospace; }}
.board th {{ color:#8FA3BF; font-weight:400; text-align:left; font-size:.78rem; letter-spacing:.12em; padding:6px 10px; border-bottom:1px solid #1B2D49; }}
.board td {{ color:{AMBER}; padding:7px 10px; font-size:.95rem; border-bottom:1px solid #101E35; white-space:nowrap; }}
.board tr:nth-child(even) td {{ background:#0A1628; }}
.board td.hot {{ color:#FF6B4A; }} .board td.ok {{ color:#4DDE9E; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {NAVY} 0%, #10315A 100%); }}
[data-testid="stSidebar"] * {{ color: #E6F0FB; }}
[data-testid="stSidebar"] .stMarkdown h3 {{ font-family:'Outfit',sans-serif; color:white; letter-spacing:.04em; }}
[data-testid="stSidebar"] label p {{ color:#BBD3EE !important; font-size:.82rem; font-weight:600; letter-spacing:.04em; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: #EAF3FB; }}
[data-testid="stSidebar"] [data-baseweb="select"] * {{ color: {NAVY} !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15); }}
.sb-brand {{ font-family:'Outfit',sans-serif; font-size:1.35rem; font-weight:700; color:white; margin-bottom:2px; }}
.sb-sub {{ font-size:.78rem; color:#9DBBDD; margin-bottom:10px; }}
.sb-count {{ font-family:'Share Tech Mono',monospace; background:rgba(255,255,255,.1); border-radius:10px; padding:8px 12px; font-size:.85rem; }}

/* ---------- misc ---------- */
div[data-testid="stPlotlyChart"] {{ background: #FFFFFF; border: 1px solid #E3ECF5; border-radius: 16px; box-shadow: 0 3px 14px rgba(11,31,58,.07); }}
div[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{ background: white; border-radius: 999px; padding: 6px 18px; }}
.stTabs [aria-selected="true"] {{ background: {SKY}; color: white; }}
</style>
"""


# --------------------------------------------------------------------------- HTML helpers
def hero(title: str, subtitle: str, tags: Iterable[str]) -> str:
    """Top banner with flight-path decoration."""
    chips = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)
    return (f'<div class="hero"><div class="cloud" style="left:48%;top:10px">☁</div>'
            f'<div class="cloud" style="left:70%;top:62px">☁</div><div class="trail"></div><div class="plane">✈</div>'
            f'<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>{chips}</div>')


def section(title: str) -> str:
    """Section header with runway-stripe underline."""
    return f'<div class="sec">{html.escape(title)}</div>'


def note(text_html: str, kind: str = "") -> str:
    """Pilot's-note call-out. ``text_html`` may contain <b> tags; callers escape dynamic strings."""
    return f'<div class="note {kind}">{text_html}</div>'


def kpi_card(label: str, value: str, sub: str = "", accent: str = SKY, delta: float | None = None,
             good_when_lower: bool = True, delta_fmt: str = "{:+.1f}", delta_unit: str = "") -> str:
    """Boarding-pass style KPI card.

    ``delta`` is the difference between the filtered selection and the full network. Colour logic:
    lower-is-better metrics (delay, cancellations) show a decrease in green.
    """
    d_html = ""
    # A (near-)zero delta carries no information (and appears on every card when no filter is active) -> hide it
    if delta is not None and pd.notna(delta) and abs(delta) >= 0.005:
        better = (delta < 0) == good_when_lower
        cls, arrow = ("delta-good" if better else "delta-bad"), ("▲" if delta > 0 else "▼")
        d_html = f'<span class="{cls}">{arrow} {delta_fmt.format(delta)}{delta_unit}</span> vs network · '
    return (f'<div class="pass" style="--accent:{accent}"><div class="lbl">{html.escape(label)}</div>'
            f'<div class="val{" sm" if len(value) > 12 else ""}">{html.escape(value)}</div><div class="sub">{d_html}{html.escape(sub)}</div></div>')


def board_table(df: pd.DataFrame, caption: str, hot_col: str | None = None, hot_threshold: float | None = None,
                headers: Sequence[str] | None = None) -> str:
    """Render a DataFrame as an amber-on-black airport departure board."""
    headers = headers or list(df.columns)
    head = "".join(f"<th>{html.escape(str(h)).upper()}</th>" for h in headers)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            cls = ""
            if hot_col and c == hot_col and hot_threshold is not None and pd.notna(v):
                cls = "hot" if v >= hot_threshold else "ok"
            cells.append(f'<td class="{cls}">{html.escape(str(v))}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="board"><div class="cap">✈ {html.escape(caption).upper()}</div>'
            f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
