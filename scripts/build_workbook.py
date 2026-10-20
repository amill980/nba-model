"""Build NBA_Model.xlsx (v0 skeleton): model logic as Excel formulas, data loaded as values.

Heavy point-in-time work stays in Python (game-log prep, line joins); every model step a
user would audit (blend, projection, edge, decision, stake, significance) is a formula.
Re-run to rebuild; inputs live in blue cells on Assumptions and Game Predictor.
"""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "NBA_Model.xlsx"
SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]
LAST = 12000  # bounded range end for Game Log lookups

A_MAP = {"gs": "GSW", "no": "NOP", "ny": "NYK", "sa": "SAS", "utah": "UTA", "wsh": "WAS"}
WINDOW = {"2022-23": "Prior (feeds 2023-24)", "2023-24": "Discovery", "2024-25": "Discovery",
          "2025-26": "Confirmation (test once)"}

F = "Arial"
base = Font(name=F, size=10)
bold = Font(name=F, size=10, bold=True)
title = Font(name=F, size=14, bold=True)
blue = Font(name=F, size=10, color="0000FF")
green = Font(name=F, size=10, color="008000")
note = Font(name=F, size=9, italic=True, color="595959")
hdr_fill = PatternFill("solid", fgColor="1F3864")
hdr_font = Font(name=F, size=10, bold=True, color="FFFFFF")
sec_fill = PatternFill("solid", fgColor="D9E1F2")
warn_fill = PatternFill("solid", fgColor="FFF2CC")
thin = Side(style="thin", color="BFBFBF")


def style_all(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.font == Font() or c.font.name != F:
                c.font = base if not c.font.bold else Font(name=F, size=10, bold=True, color=c.font.color)


def header(ws, row, labels, col=1):
    for i, t in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=t)
        c.font, c.fill = hdr_font, hdr_fill
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")


def section(ws, row, text, ncols=3):
    for i in range(ncols):
        ws.cell(row=row, column=1 + i).fill = sec_fill
    ws.cell(row=row, column=1, value=text).font = bold


# ---------------------------------------------------------------- data prep
frames = []
for s in SEASONS:
    p = ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv"
    if p.exists() and p.stat().st_size > 5:
        d = pd.read_csv(p)
        if len(d):
            d["season"] = s
            frames.append(d)
gl = pd.concat(frames, ignore_index=True)
opp = gl[["GAME_ID", "TEAM_ID", "PTS"]].rename(columns={"TEAM_ID": "OPP_ID", "PTS": "OPP_PTS"})
gl = gl.merge(opp, on="GAME_ID")
gl = gl[gl.TEAM_ID != gl.OPP_ID].sort_values(["GAME_DATE", "GAME_ID", "TEAM_ABBREVIATION"]).reset_index(drop=True)
TEAMS = sorted(gl.TEAM_ABBREVIATION.unique())
assert len(TEAMS) == 30, TEAMS

wb = Workbook()

# ---------------------------------------------------------------- README
ws = wb.active; ws.title = "README"
lines = [
    ("NBA Betting Model: research workbook (v1 ratings model)", title),
    ("Built 2026-10-19, refreshed after the 2025-26 confirmation test. Projects spread/total/win probability from team ratings and compares with the book.", base),
    ("", base),
    ("STATUS: NOT A BETTING TOOL. The v1 model FAILED its signed 2025-26 confirmation test (spread closing-line value +0.35 pts vs the +0.5 bar; totals +0.03). Player availability is real information but the closing line already prices it. See docs/Confirmation_Results.md and docs/Injury_v2_findings.md. Current work is the live 2026-27 timing study (docs/Live_Study_Plan.md).", bold),
    ("", base),
    ("Colour code: blue = input you may edit; black = formula; green = link to another tab; yellow fill = caution/placeholder.", base),
    ("Tabs", bold),
    ("  Assumptions: every tunable constant with source/notes. K, home court, rest, 3-in-4 and margin SD were tuned on the discovery seasons only; edge thresholds and stake tiers are still placeholders.", base),
    ("  Team Ratings: prior-season and current-season ORtg/DRtg/Pace per team, blended by shrinkage. Not opponent-adjusted (tested, no accuracy gain).", base),
    ("  Game Predictor: pick two teams, enter rest + market lines (example values shown), read projection, edge, decision, stake, moneyline edge.", base),
    ("  Edge Significance: win/loss record vs. breakeven at the price taken (z-test, Wilson interval). Example record shown.", base),
    ("  Backtest and Edge Sweep: DISCOVERY seasons only (2023-24, 2024-25). Point-in-time ratings, projection and results are formulas; sweeps show win rate by edge size graded at the close and at the open, with closing-line value.", base),
    ("  Lines (ESPN): the lines behind the backtest and the confirmation run: ESPN BET open/close (DraftKings for part of 2025-26), joined to verified scores. 2025-26 rows are the confirmation season (already used).", base),
    ("  Game Log: team-game rows 2022-23 onward (nba_api; every score matches ESPN). Possessions and pace are formulas.", base),
    ("  Bet Log (Locked): headers only. Odds Archive: the latest odds snapshot only; full history in data/odds/odds_archive.csv.", base),
    ("", base),
    ("DATA: Kaggle file A (nba_2008-2026.csv) was used only to cross-check provenance. It equals ESPN BET closing lines for 2023-25 but not 2025-26, so it is not used. Moneyline history for the backtest is in the Lines (ESPN) tab (close and open) but no moneyline backtest has been run.", bold),
    ("Windows: 2022-23 = prior only; 2023-24 and 2024-25 = discovery; 2025-26 = confirmation (run once on 2026-10-19, failed, now exposed); 2026-27 = live study, scored on closing-line value only.", base),
    ("Daily collection runs outside this workbook (Python scripts under Windows Task Scheduler writing CSVs in data/). This file is rebuilt with scripts/build_workbook.py; it has no macros and is not refreshed automatically.", base),
    ("Spec: docs/NBA_Model_Spec.md. Data gates: data/gates/. Findings: docs/Backtest_Findings.md.", base),
]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t); c.font = f; c.alignment = Alignment(wrap_text=True, vertical="top")
ws.column_dimensions["A"].width = 150
ws["A4"].fill = warn_fill; ws["A17"].fill = warn_fill

# ---------------------------------------------------------------- Assumptions
wa = wb.create_sheet("Assumptions")
wa["A1"] = "Assumptions"; wa["A1"].font = title
wa["A2"] = "Edit only blue cells. Rating parameters (K, HCA, rest, 3-in-4, SD) were tuned on the discovery seasons only (2023-24, 2024-25) by margin accuracy, never by betting results. Thresholds and stakes are still placeholders. Never tune on 2025-26."
wa["A2"].font = note
header(wa, 3, ["Setting", "Value", "Source / notes"])
rows = [
    (4, "SEASON SETUP", None, None),
    (5, "Current season", "2026-27", "Season being rated. Change each October."),
    (6, "Prior season", "2025-26", "Feeds the shrinkage prior."),
    (8, "RATING MODEL", None, None),
    (9, "Prior-season shrinkage K (games)", 10, "Blended = (K*prior + GP*current)/(K+GP). TUNED on discovery by 2-fold out-of-sample margin RMSE (scripts/tune_v1.py): raw ratings best at K=10; WNBA used 10, CFB 3. Year-over-year team-strength correlation is only 0.25-0.60, so the prior carries little."),
    (10, "League home-court advantage (pts)", 1.94, "TUNED: least-squares intercept on discovery seasons (both folds averaged)."),
    (11, "Margin standard deviation (pts)", 14.1, "Residual RMSE of the tuned model vs actual margin on discovery (out-of-sample, 14.12). Market close RMSE is 13.56. Used for win probability; still needs a calibration check."),
    (12, "League average ORtg (pts/100 poss)", "=AVERAGE('Team Ratings'!J5:J34)", "Formula: mean of blended team ORtg."),
    (13, "League average pace (poss/48)", "=AVERAGE('Team Ratings'!L5:L34)", "Formula."),
    (15, "REST AND FATIGUE", None, None),
    (16, "Rest differential coefficient (pts per day)", 1.35, "TUNED on discovery (least squares, rest diff capped at +/-3 days); WNBA value was 1.0."),
    (17, "Rest differential cap (days)", 3, "Carried over from WNBA model."),
    (18, "3-games-in-4-nights penalty (pts, negative)", -0.59, "TUNED on discovery (least squares); WNBA value was -1.5. Small and likely noisy."),
    (20, "BETTING THRESHOLDS", None, None),
    (21, "Min spread edge to bet (pts)", 1.5, "WNBA/CFB carryover; the NBA threshold must be chosen on discovery data only."),
    (22, "Min total edge to bet (pts)", 1.5, "As above."),
    (23, "Min moneyline edge (probability points)", 0.03, "PLACEHOLDER (3 percentage points)."),
    (24, "Standard price (American)", -110, "Breakeven 52.38% at -110."),
]
for r, a, b, c in rows:
    if b is None and c is None:
        section(wa, r, a); continue
    wa.cell(row=r, column=1, value=a)
    cell = wa.cell(row=r, column=2, value=b)
    cell.font = base if (isinstance(b, str) and b.startswith("=")) else blue
    wa.cell(row=r, column=3, value=c).font = note
    if isinstance(b, (int, float)) and r in (9, 10, 11, 16, 17, 18, 21, 22, 23): cell.fill = warn_fill
section(wa, 25, "STAKE TIERS (units: $; WNBA/CFB carryover)")
header(wa, 26, ["Min |edge| (pts)", "Bet size ($)", "Notes"])
for i, (e, s) in enumerate([(1.5, 10), (3, 15), (5, 25), (8, 35)]):
    wa.cell(row=27 + i, column=1, value=e).font = blue
    wa.cell(row=27 + i, column=2, value=s).font = blue
wa["C27"] = "Largest threshold <= |edge| applies. Replace with a Kelly-style rule only after calibration."; wa["C27"].font = note
section(wa, 32, "VALIDATION WINDOWS (pre-registered in spec)")
for i, t in enumerate(["2022-23: prior only", "2023-24, 2024-25: discovery (tuning allowed)", "2025-26: confirmation (test once, no tuning)", "2026-27: live pre-registered test after model freeze"]):
    wa.cell(row=33 + i, column=1, value=t)
wa.column_dimensions["A"].width = 46; wa.column_dimensions["B"].width = 16; wa.column_dimensions["C"].width = 110

# ---------------------------------------------------------------- Game Log
wg = wb.create_sheet("Game Log")
cols = ["Season", "Date", "Game ID", "Team", "Matchup", "Home?", "W/L", "MIN", "PTS", "Opp PTS", "FGA", "FTA", "OREB", "TOV", "Possessions", "Pace (poss/48)"]
header(wg, 1, cols)
for i, r in enumerate(gl.itertuples(index=False), 2):
    vals = [r.season, r.GAME_DATE, str(r.GAME_ID), r.TEAM_ABBREVIATION, r.MATCHUP,
            f'=IF(ISNUMBER(SEARCH("@",E{i})),"No","Yes")', r.WL, int(r.MIN), int(r.PTS), int(r.OPP_PTS),
            int(r.FGA), int(r.FTA), int(r.OREB), int(r.TOV), f"=K{i}+0.44*L{i}-M{i}+N{i}", f"=48*O{i}/(H{i}/5)"]
    for j, v in enumerate(vals, 1):
        wg.cell(row=i, column=j, value=v)
NGL = len(gl) + 1
wg.freeze_panes = "A2"
for j, w in enumerate([9, 11, 12, 7, 14, 7, 5, 6, 6, 8, 6, 6, 6, 6, 12, 14], 1):
    wg.column_dimensions[get_column_letter(j)].width = w

# ---------------------------------------------------------------- Team Ratings
wt = wb.create_sheet("Team Ratings", 2)
wt["A1"] = "Team Ratings"; wt["A1"].font = title
wt["A2"] = ("v0: raw (not opponent-adjusted) ratings per 100 possessions from Game Log. DRtg uses own possessions as the denominator "
            "(standard approximation). Blended = (K*prior + GP*current)/(K+GP) applied separately to ORtg, DRtg and Pace.")
wt["A2"].font = note
header(wt, 4, ["Team", "Prior GP", "Prior ORtg", "Prior DRtg", "Prior Pace", "Cur GP", "Cur ORtg", "Cur DRtg", "Cur Pace",
               "Blended ORtg", "Blended DRtg", "Blended Pace", "Blended Net", "Team HCA (pts)", "Recent form adj (pts)",
               "Injury adj (pts)", "Power rating (pts)"])
GLR = lambda col: f"'Game Log'!${col}$2:${col}${LAST}"
for i, t in enumerate(TEAMS):
    r = 5 + i
    wt.cell(row=r, column=1, value=t)
    for off, season_ref, cols_ in ((0, "Assumptions!$B$6", (2, 3, 4, 5)), (4, "Assumptions!$B$5", (6, 7, 8, 9))):
        gp, off_c, def_c, pace_c = cols_
        crit = f"{GLR('A')},{season_ref},{GLR('D')},$A{r}"
        wt.cell(row=r, column=gp, value=f"=COUNTIFS({crit})").font = green
        wt.cell(row=r, column=off_c, value=f"=IF({get_column_letter(gp)}{r}=0,0,100*SUMIFS({GLR('I')},{crit})/SUMIFS({GLR('O')},{crit}))").font = green
        wt.cell(row=r, column=def_c, value=f"=IF({get_column_letter(gp)}{r}=0,0,100*SUMIFS({GLR('J')},{crit})/SUMIFS({GLR('O')},{crit}))").font = green
        wt.cell(row=r, column=pace_c, value=f"=IF({get_column_letter(gp)}{r}=0,0,AVERAGEIFS({GLR('P')},{crit}))").font = green
    for col, (pc, cc) in zip((10, 11, 12), (("C", "G"), ("D", "H"), ("E", "I"))):
        wt.cell(row=r, column=col, value=f"=(Assumptions!$B$9*{pc}{r}+F{r}*{cc}{r})/(Assumptions!$B$9+F{r})")
    wt.cell(row=r, column=13, value=f"=J{r}-K{r}")
    wt.cell(row=r, column=14, value="=Assumptions!$B$10").font = green
    wt.cell(row=r, column=15, value=0).font = blue
    wt.cell(row=r, column=16, value=0).font = blue
    wt.cell(row=r, column=17, value=f"=M{r}+O{r}+P{r}")
    for col in (3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17): wt.cell(row=r, column=col).number_format = "0.0"
wt.freeze_panes = "B5"
wt.column_dimensions["A"].width = 8
for j in range(2, 18): wt.column_dimensions[get_column_letter(j)].width = 12
wt.row_dimensions[4].height = 42

# ---------------------------------------------------------------- Game Predictor
wp = wb.create_sheet("Game Predictor", 3)
wp["A1"] = "Game Predictor"; wp["A1"].font = title
wp["A2"] = "Pick teams, enter rest and market lines. Values in blue are an EXAMPLE (not a real market line); replace them."
wp["A2"].font = note
header(wp, 3, ["Item", "Value", "Notes"])
TR = "'Team Ratings'!"
def idx(col, team_cell): return f"INDEX({TR}${col}$5:${col}$34,MATCH({team_cell},{TR}$A$5:$A$34,0))"
inp = [
    (4, "Home team", "BOS", "Team abbreviation (dropdown)."),
    (5, "Away team", "NYK", "Team abbreviation (dropdown)."),
    (6, "Home rest days (days since last game, minus 1)", 1, "WNBA convention: 0 = back-to-back."),
    (7, "Away rest days", 2, ""),
    (8, "Home team playing 3rd game in 4 nights?", "No", "Yes/No."),
    (9, "Away team playing 3rd game in 4 nights?", "No", "Yes/No."),
    (11, "Market home spread (book notation, e.g. -3.5 = home favoured)", -3.5, "EXAMPLE value."),
    (12, "Market total", 224.5, "EXAMPLE value."),
    (13, "Market moneyline, home (American)", -160, "EXAMPLE value."),
    (14, "Market moneyline, away (American)", 140, "EXAMPLE value."),
]
for r, a, b, c in inp:
    wp.cell(row=r, column=1, value=a); wp.cell(row=r, column=2, value=b).font = blue; wp.cell(row=r, column=3, value=c).font = note
section(wp, 16, "PROJECTION")
out = [
    (17, "Home blended ORtg", f"={idx('J','$B$4')}"),
    (18, "Home blended DRtg", f"={idx('K','$B$4')}"),
    (19, "Away blended ORtg", f"={idx('J','$B$5')}"),
    (20, "Away blended DRtg", f"={idx('K','$B$5')}"),
    (21, "Expected pace (poss/48)", f"=({idx('L','$B$4')}+{idx('L','$B$5')})/2"),
    (22, "Home projected points", "=B21*(B17+B20-Assumptions!$B$12)/100"),
    (23, "Away projected points", "=B21*(B19+B18-Assumptions!$B$12)/100"),
    (24, "Home-court advantage (pts)", f"={idx('N','$B$4')}"),
    (25, "Rest adjustment (pts to home margin)", "=Assumptions!$B$16*MAX(-Assumptions!$B$17,MIN(Assumptions!$B$17,B6-B7))"),
    (26, "Fatigue adjustment (pts to home margin)", '=IF(B8="Yes",Assumptions!$B$18,0)-IF(B9="Yes",Assumptions!$B$18,0)'),
    (27, "Form + injury adjustment (pts to home margin)", f"=({idx('O','$B$4')}+{idx('P','$B$4')})-({idx('O','$B$5')}+{idx('P','$B$5')})"),
    (28, "Projected home margin (+ = home wins)", "=B22-B23+B24+B25+B26+B27"),
    (29, "Projected home spread (book notation)", "=-B28"),
    (30, "Projected total", "=B22+B23"),
]
for r, a, f_ in out:
    wp.cell(row=r, column=1, value=a); c = wp.cell(row=r, column=2, value=f_)
    c.font = green if r in (17, 18, 19, 20, 21, 24, 27) else base
    c.number_format = "0.0"
section(wp, 32, "EDGE AND DECISION (spread / total)")
dec = [
    (33, "Spread edge (projected margin + market home spread)", "=B28+B11", "Positive = model likes home more than the market does."),
    (34, "Spread decision", '=IF(B11="","No Line",IF(B33>=Assumptions!$B$21,"Bet Home",IF(B33<=-Assumptions!$B$21,"Bet Away","No Bet")))', ""),
    (35, "Total edge (projected - market)", "=B30-B12", ""),
    (36, "Total decision", '=IF(B12="","No Line",IF(B35>=Assumptions!$B$22,"Bet Over",IF(B35<=-Assumptions!$B$22,"Bet Under","No Bet")))', ""),
    (37, "Stake, spread bet ($)", '=IF(OR(B34="Bet Home",B34="Bet Away"),LOOKUP(ABS(B33),Assumptions!$A$27:$A$30,Assumptions!$B$27:$B$30),0)', "Tier table on Assumptions."),
]
for r, a, f_, n in dec:
    wp.cell(row=r, column=1, value=a); c = wp.cell(row=r, column=2, value=f_); wp.cell(row=r, column=3, value=n).font = note
    if r in (33, 35): c.number_format = "0.0"
section(wp, 39, "MONEYLINE")
ml = [
    (40, "Model P(home wins)", "=NORMSDIST(B28/Assumptions!$B$11)", "Normal margin model; SD on Assumptions (needs calibration)."),
    (41, "Implied P home (with vig)", "=IF(B13<0,-B13/(-B13+100),100/(B13+100))", ""),
    (42, "Implied P away (with vig)", "=IF(B14<0,-B14/(-B14+100),100/(B14+100))", ""),
    (43, "Fair P home (vig removed)", "=B41/(B41+B42)", "Multiplicative method (as in the CFB workbook); approximate on lopsided prices."),
    (44, "Moneyline edge, home (prob. points)", "=B40-B43", ""),
    (45, "Moneyline decision", '=IF(B44>=Assumptions!$B$23,"Bet Home ML",IF(-B44>=Assumptions!$B$23,"Bet Away ML","No Bet"))', ""),
]
for r, a, f_, n in ml:
    wp.cell(row=r, column=1, value=a); c = wp.cell(row=r, column=2, value=f_); wp.cell(row=r, column=3, value=n).font = note
    c.number_format = "0.0%" if r in (40, 41, 42, 43, 44) else "General"
dv = DataValidation(type="list", formula1=f"={TR}$A$5:$A$34", allow_blank=False); wp.add_data_validation(dv); dv.add("B4"); dv.add("B5")
dv2 = DataValidation(type="list", formula1='"Yes,No"'); wp.add_data_validation(dv2); dv2.add("B8"); dv2.add("B9")
wp.column_dimensions["A"].width = 58; wp.column_dimensions["B"].width = 14; wp.column_dimensions["C"].width = 80

# ---------------------------------------------------------------- Edge Significance
we = wb.create_sheet("Edge Significance", 4)
we["A1"] = "Edge Significance"; we["A1"].font = title
we["A2"] = "Compares an actual record with the breakeven rate at the price taken. EXAMPLE record below (replace with the Bet Log (Locked) tally)."
we["A2"].font = note
header(we, 3, ["Item", "Value", "Notes"])
es = [
    (4, "Wins", 55, "EXAMPLE"), (5, "Losses", 45, "EXAMPLE"), (6, "Pushes", 0, ""),
    (7, "Price taken (American)", "=Assumptions!B24", ""),
    (9, "Breakeven win rate", "=IF(B7<0,-B7/(-B7+100),100/(B7+100))", "Pushes excluded from n."),
    (10, "Bets decided (n)", "=B4+B5", ""),
    (11, "Observed win rate", "=IF(B10=0,0,B4/B10)", ""),
    (12, "z vs. breakeven", "=IF(B10=0,0,(B11-B9)/SQRT(B9*(1-B9)/B10))", ""),
    (13, "One-sided p-value", "=1-NORMSDIST(B12)", "p < 0.05 is the project's bar; report next to the rate."),
    (14, "Wilson 95% lower bound", "=IF(B10=0,0,(B11+1.96^2/(2*B10)-1.96*SQRT(B11*(1-B11)/B10+1.96^2/(4*B10^2)))/(1+1.96^2/B10))", ""),
    (15, "Wilson 95% upper bound", "=IF(B10=0,0,(B11+1.96^2/(2*B10)+1.96*SQRT(B11*(1-B11)/B10+1.96^2/(4*B10^2)))/(1+1.96^2/B10))", ""),
]
for r, a, b, c in es:
    we.cell(row=r, column=1, value=a)
    cell = we.cell(row=r, column=2, value=b); we.cell(row=r, column=3, value=c).font = note
    if r in (4, 5, 6): cell.font = blue
    if r in (9, 11, 14, 15): cell.number_format = "0.0%"
    if r in (12, 13): cell.number_format = "0.000"
we.column_dimensions["A"].width = 34; we.column_dimensions["B"].width = 14; we.column_dimensions["C"].width = 60

# ---------------------------------------------------------------- Lines (ESPN)
wl = wb.create_sheet("Lines (ESPN)")
frames_l = []
for fn in ("pit_games.csv", "pit_confirmation.csv"):
    pth = ROOT / "data/backtest" / fn
    if pth.exists(): frames_l.append(pd.read_csv(pth))
LN = pd.concat(frames_l, ignore_index=True) if frames_l else pd.DataFrame()
hdr = ["Season", "Window", "Date", "Home", "Away", "Book", "Home spread OPEN", "Home spread CLOSE", "Total OPEN", "Total CLOSE",
       "ML home close", "ML away close", "Home PTS", "Away PTS", "Home margin", "Spread result (close)", "Total result (close)", "Source"]
header(wl, 1, hdr)
for n, r in enumerate(LN.itertuples(index=False), 2):
    vals = [r.season, "Discovery" if r.window == "Discovery" else "Confirmation (used once)", r.date, r.home, r.away, r.book,
            r.open_home_spread, r.mkt_home_spread, r.open_total, r.mkt_total,
            None if pd.isna(r.ml_home_close) else int(r.ml_home_close), None if pd.isna(r.ml_away_close) else int(r.ml_away_close),
            int(r.home_pts), int(r.away_pts), f"=M{n}-N{n}",
            f'=IF(O{n}+H{n}>0,"Home",IF(O{n}+H{n}<0,"Away","Push"))', f'=IF(M{n}+N{n}>J{n},"Over",IF(M{n}+N{n}<J{n},"Under","Push"))',
            "ESPN core odds API (open/close)"]
    for j, v in enumerate(vals, 1): wl.cell(row=n, column=j, value=v)
wl.freeze_panes = "A2"
for j, w in enumerate([9, 24, 11, 7, 7, 11, 11, 11, 10, 10, 10, 10, 9, 9, 9, 12, 12, 30], 1): wl.column_dimensions[get_column_letter(j)].width = w
wl.row_dimensions[1].height = 42
n = len(LN) + 2

# ---------------------------------------------------------------- Bet Log, Odds Archive
wbl = wb.create_sheet("Bet Log (Locked)")
header(wbl, 1, ["Date", "Market", "Home", "Away", "Bet", "Line", "Price", "Model edge", "Stake ($)", "Result", "Profit ($)", "Closing line", "CLV (pts)", "Logged at (UTC)"])
wbl["A3"] = "Header only. Values are pasted/logged here once a game is graded; never recomputed. Filled by the daily run (later step)."; wbl["A3"].font = note
wo = wb.create_sheet("Odds Archive")
header(wo, 1, ["captured_utc", "event_id", "commence_time_utc", "home", "away", "book", "market", "outcome", "price", "point"])
arch = ROOT / "data/odds/odds_archive.csv"
if arch.exists():
    ad = pd.read_csv(arch)
    if len(ad):
        ad = ad[ad.captured_utc == ad.captured_utc.max()]   # workbook shows the LATEST snapshot only; full history stays in the CSV
        for i, rec in enumerate(ad.to_dict("records"), 3):
            for j, col in enumerate(["captured_utc", "event_id", "commence_time_utc", "home", "away", "book", "market", "outcome", "price", "point"], 1):
                v = rec[col]; wo.cell(row=i, column=j, value=None if pd.isna(v) else v)
wo["A2"] = "Latest snapshot only (full history: data/odds/odds_archive.csv, built by scripts/load_odds_archive.py from data/odds/raw/*.json)."; wo["A2"].font = note


# ---------------------------------------------------------------- Backtest + Edge Sweep (discovery seasons)
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent))
if (ROOT / "data/backtest/pit_games.csv").exists():
    import backtest_sheets
    backtest_sheets.add(wb, pd.read_csv(ROOT / "data/backtest/pit_games.csv"),
                        dict(header=header, section=section, title=title, note=note, blue=blue))

# fonts: Arial everywhere
for w in wb.worksheets:
    for row in w.iter_rows():
        for c in row:
            if c.value is not None and c.font.name != F:
                c.font = Font(name=F, size=10)
wb.save(OUT)
print("saved", OUT, "| game-log rows:", len(gl), "| lines rows:", n - 2)
