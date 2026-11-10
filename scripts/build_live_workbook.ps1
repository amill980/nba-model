# Builds NBA_Live.xlsx: a Power Query workbook that reads the daily CSVs. Press Data > Refresh All to update.
# Needs desktop Excel. Re-running replaces NBA_Live.xlsx (queries are defined here, not by hand).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out  = Join-Path $root 'NBA_Live.xlsx'
$q = '"'

function Csv($rel) { "Csv.Document(File.Contents(`"$root\$rel`"),[Delimiter=`",`", Encoding=65001, QuoteStyle=QuoteStyle.Csv])" }

$queries = [ordered]@{
 'Today' = @"
let
    Source = $(Csv 'docs\daily\latest.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Keep = Table.SelectColumns(Promoted, {"report_date","tip_et","line_status","line_as_of_et","game","model_line","market_line","model_home_margin","consensus_home_spread","spread_range","spread_edge","spread_edge_bovada","spread_flag","best_bettable_spread","model_total","consensus_total","total_range","total_edge","total_edge_bovada","total_flag","best_bettable_total","bovada_spread_total","draftkings_spread_total","games_played_home_away","injury_report_out","snapshot_utc"}),
    Typed = Table.TransformColumnTypes(Keep, {{"model_home_margin", type number},{"consensus_home_spread", type number},{"spread_edge", type number},{"spread_edge_bovada", type number},{"model_total", type number},{"consensus_total", type number},{"total_edge", type number},{"total_edge_bovada", type number}}),
    Renamed = Table.RenameColumns(Typed, {{"report_date","Date"},{"tip_et","Tip (ET)"},{"line_status","Line status"},{"line_as_of_et","Line as of (ET)"},{"game","Game"},{"model_line","Model line (home)"},{"market_line","Market line (home, middle)"},{"model_home_margin","Model margin (home +)"},{"consensus_home_spread","Middle of market spread (home)"},{"spread_range","Spread range across books"},{"spread_edge","Spread edge vs middle"},{"spread_edge_bovada","Spread edge vs Bovada"},{"spread_flag","Spread flag"},{"best_bettable_spread","Best bettable spread"},{"model_total","Model total"},{"consensus_total","Middle of market total"},{"total_range","Total range across books"},{"total_edge","Total edge vs middle"},{"total_edge_bovada","Total edge vs Bovada"},{"total_flag","Total flag"},{"best_bettable_total","Best bettable total"},{"bovada_spread_total","Bovada spread / total"},{"draftkings_spread_total","DraftKings spread / total"},{"games_played_home_away","Games played (home/away)"},{"injury_report_out","Out / Doubtful (info only)"},{"snapshot_utc","Odds snapshot (UTC)"}})
in
    Renamed
"@
 'Odds' = @"
let
    Source = $(Csv 'data\odds\odds_archive.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Pre = Table.SelectRows(Promoted, each [pregame] = "True" and [market] <> "h2h"),
    Typed = Table.TransformColumnTypes(Pre, {{"price", Int64.Type},{"point", type number}}),
    Maxes = Table.Group(Typed, {"event_id"}, {{"maxcap", each List.Max([captured_utc]), type text}}),
    Joined = Table.NestedJoin(Typed, {"event_id"}, Maxes, {"event_id"}, "m", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "m", {"maxcap"}),
    Latest = Table.SelectRows(Expanded, each [captured_utc] = [maxcap]),
    Cols = Table.SelectColumns(Latest, {"captured_utc","game_date_et","commence_time_utc","away","home","book","market","outcome","point","price"})
in
    Cols
"@
 'Closing' = @"
let
    Source = $(Csv 'data\odds\closing_lines.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Rows = Table.SelectRows(Promoted, each [market] <> "h2h"),
    Typed = Table.TransformColumnTypes(Rows, {{"price", Int64.Type},{"point", type number},{"minutes_before_tip", type number}}),
    Cols = Table.SelectColumns(Typed, {"game_date_et","away","home","book","market","outcome","point","price","captured_utc","minutes_before_tip","close_quality"}),
    Sorted = Table.Sort(Cols, {{"game_date_et", Order.Descending},{"home", Order.Ascending},{"market", Order.Ascending},{"book", Order.Ascending}})
in
    Sorted
"@
 'Injuries' = @"
let
    Source = $(Csv 'data\injuries\injury_status.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    WithDates = Table.AddColumn(Promoted, "ReportDT", each try DateTime.FromText([report_time_et], [Format="MM/dd/yy hh:mm tt", Culture="en-US"]) otherwise null, type nullable datetime),
    WithGame = Table.AddColumn(WithDates, "GameDate", each try Date.FromText([game_date], [Format="MM/dd/yyyy", Culture="en-US"]) otherwise null, type nullable date),
    Recent = Table.SelectRows(WithGame, each [GameDate] <> null and [GameDate] >= Date.From(DateTime.LocalNow()) and [GameDate] <= Date.AddDays(Date.From(DateTime.LocalNow()), 1) and [status] <> "NOT_YET_SUBMITTED"),
    Sorted = Table.Buffer(Table.Sort(Recent, {{"ReportDT", Order.Descending}})),
    Latest = Table.Distinct(Sorted, {"game_date","team","player"}),
    Cols = Table.SelectColumns(Latest, {"game_date","game_time_et","matchup","team","player","status","reason_on_line","report_time_et"})
in
    Cols
"@
 'Results' = @"
let
    Source = $(Csv 'data\games\team_games_2026-27_Regular_Season.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Cols = Table.SelectColumns(Promoted, {"GAME_DATE","TEAM_ABBREVIATION","MATCHUP","WL","PTS","PLUS_MINUS"}),
    Sorted = Table.Sort(Cols, {{"GAME_DATE", Order.Descending}}),
    Top = Table.FirstN(Sorted, 120)
in
    Top
"@
 'Players' = @"
let
    Source = $(Csv 'data\profiles\player_profiles.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Keep = Table.SelectColumns(Promoted, {"player","team","position","height_in","age","nba_exp","gp","games_missed","mpg","mpg_last5","mpg_last10","mpg_trend_last10_vs_season","minutes_rank_on_team","pts","reb","ast","pts_per36","ts_pct","fg3_pct","ft_pct","usage_proxy_per36","prior_mpg","prior_pts_per36","latest_injury_status","latest_status_game_date","times_listed_out_or_doubtful","how_acquired"}),
    Typed = Table.TransformColumnTypes(Keep, {{"height_in", Int64.Type},{"age", type number},{"gp", Int64.Type},{"games_missed", Int64.Type},{"mpg", type number},{"mpg_last5", type number},{"mpg_last10", type number},{"mpg_trend_last10_vs_season", type number},{"pts", type number},{"reb", type number},{"ast", type number},{"pts_per36", type number},{"ts_pct", type number},{"fg3_pct", type number},{"ft_pct", type number},{"usage_proxy_per36", type number},{"prior_mpg", type number},{"prior_pts_per36", type number}}),
    Sorted = Table.Sort(Typed, {{"team", Order.Ascending},{"mpg", Order.Descending}})
in
    Sorted
"@
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  if (Test-Path $out) { Remove-Item $out -Force }
  $wb = $xl.Workbooks.Add()
  while ($wb.Worksheets.Count -gt 1) { $wb.Worksheets.Item($wb.Worksheets.Count).Delete() }
  $readme = $wb.Worksheets.Item(1); $readme.Name = 'README'
  $text = @(
   'NBA Live: refresh workbook (reads the daily CSVs; does not fetch data itself)',
   '',
   'HOW TO USE: Data > Refresh All. The tabs update from the files the scheduled tasks write in the project folder.',
   'The odds-driven tabs (Today, Odds, Closing) refresh themselves every minute while this workbook is open, and on open; the others every 10 minutes. Data > Refresh All forces it.',
   'If a tab is empty, the file it reads has no rows yet (for example Results before the first game is played).',
   '',
   'Today: model projections vs the market (docs\daily\latest.csv, rewritten at 12:00 and 6:40 PM ET on game days).',
   'Odds: the latest PRE-GAME snapshot per game, spreads and totals, every book (in-play lines from games already started are excluded).',
   'Closing: the locked closing line for each game already started: the last pre-game snapshot, with minutes before tip and a quality label (locked = within 20 minutes of tip).',
   'Injuries: latest Out / Doubtful statuses for games today and tomorrow (informational only; the model does not use them).',
   'Results: the 120 most recent 2026-27 team results (refreshed by the 6:30 AM task).',
   'Players: profiles of every player averaging 15+ minutes over 5+ games (bio, minutes, production, injury status; descriptive only). Rebuilt each morning.',
   'Health: last data-collection health check (counts only).',
   '',
   'NOT A RECOMMENDATION. The v1 model failed its signed 2025-26 confirmation test and has no demonstrated edge (docs\Confirmation_Results.md).',
   '"Middle of market" is the median across books; with an even number of books it can fall between two posted numbers, so it may not be a line anyone offers. Use the range and the Bovada/DraftKings columns.',
   'Queries read absolute paths under: ' + $root + '. If the folder moves, edit the file paths in Data > Queries & Connections.'
  )
  for ($i=0; $i -lt $text.Count; $i++) { $readme.Cells.Item($i+1,1).Value2 = $text[$i] }
  $readme.Cells.Item(1,1).Font.Bold = $true; $readme.Cells.Item(1,1).Font.Size = 14
  $readme.Columns.Item(1).ColumnWidth = 150

  $sheetFor = @{ 'Today'='Today'; 'Odds'='Odds'; 'Closing'='Closing'; 'Injuries'='Injuries'; 'Results'='Results'; 'Players'='Players' }
  foreach ($name in $queries.Keys) {
    [void]$wb.Queries.Add($name, $queries[$name])
    $ws = $wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count))
    $ws.Name = $sheetFor[$name]
    $conn = "OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=`$Workbook`$;Location=$name;Extended Properties=`"`""
    $lo = $ws.ListObjects.Add(0, $conn, $true, 1, $ws.Range('A1'))
    $lo.QueryTable.CommandType = 2
    $lo.QueryTable.CommandText = "SELECT * FROM [$name]"
    $lo.QueryTable.BackgroundQuery = $false
    $lo.QueryTable.RefreshStyle = 1
    $lo.QueryTable.Refresh($false) | Out-Null
    # auto-refresh while the workbook is open: every minute for the odds-driven tabs, every 10 minutes for the rest
    $lo.QueryTable.RefreshOnFileOpen = $true
    $lo.QueryTable.RefreshPeriod = $(if ($name -in 'Today','Odds','Closing') { 1 } else { 10 })
    $lo.TableStyle = 'TableStyleMedium2'
    $ws.UsedRange.Columns.AutoFit() | Out-Null
  }
  # Health tab: plain text of the newest health file, refreshed by a small query
  $mh = @"
let
    Files = Folder.Files("$root\data\health"),
    Newest = Table.FirstN(Table.Sort(Files, {{"Date modified", Order.Descending}}), 1),
    Lines = Table.FromList(Lines.FromBinary(Newest{0}[Content]), Splitter.SplitByNothing(), {"Health check (latest)"})
in
    Lines
"@
  [void]$wb.Queries.Add('Health', $mh)
  $wh = $wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count)); $wh.Name = 'Health'
  $lo = $wh.ListObjects.Add(0, "OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=`$Workbook`$;Location=Health;Extended Properties=`"`"", $true, 1, $wh.Range('A1'))
  $lo.QueryTable.CommandType = 2; $lo.QueryTable.CommandText = 'SELECT * FROM [Health]'; $lo.QueryTable.BackgroundQuery = $false
  $lo.QueryTable.Refresh($false) | Out-Null; $wh.Columns.Item(1).ColumnWidth = 120
  $wb.Worksheets.Item('Today').Activate()
  $wb.SaveAs($out, 51)   # xlsx
  $wb.Close($false)
  "saved $out"
} finally { $xl.Quit() }
