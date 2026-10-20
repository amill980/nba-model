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
    Keep = Table.SelectColumns(Promoted, {"report_date","tip_et","game","model_home_margin","consensus_home_spread","spread_range","spread_edge","spread_edge_bovada","spread_flag","best_bettable_spread","model_total","consensus_total","total_range","total_edge","total_edge_bovada","total_flag","best_bettable_total","bovada_spread_total","draftkings_spread_total","games_played_home_away","injury_report_out","snapshot_utc"}),
    Typed = Table.TransformColumnTypes(Keep, {{"model_home_margin", type number},{"consensus_home_spread", type number},{"spread_edge", type number},{"spread_edge_bovada", type number},{"model_total", type number},{"consensus_total", type number},{"total_edge", type number},{"total_edge_bovada", type number}}),
    Renamed = Table.RenameColumns(Typed, {{"report_date","Date"},{"tip_et","Tip (ET)"},{"game","Game"},{"model_home_margin","Model margin (home +)"},{"consensus_home_spread","Middle of market spread (home)"},{"spread_range","Spread range across books"},{"spread_edge","Spread edge vs middle"},{"spread_edge_bovada","Spread edge vs Bovada"},{"spread_flag","Spread flag"},{"best_bettable_spread","Best bettable spread"},{"model_total","Model total"},{"consensus_total","Middle of market total"},{"total_range","Total range across books"},{"total_edge","Total edge vs middle"},{"total_edge_bovada","Total edge vs Bovada"},{"total_flag","Total flag"},{"best_bettable_total","Best bettable total"},{"bovada_spread_total","Bovada spread / total"},{"draftkings_spread_total","DraftKings spread / total"},{"games_played_home_away","Games played (home/away)"},{"injury_report_out","Out / Doubtful (info only)"},{"snapshot_utc","Odds snapshot (UTC)"}})
in
    Renamed
"@
 'Odds' = @"
let
    Source = $(Csv 'data\odds\odds_archive.csv'),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"price", Int64.Type},{"point", type number}}),
    Latest = List.Max(Typed[captured_utc]),
    Rows = Table.SelectRows(Typed, each [captured_utc] = Latest and [market] <> "h2h"),
    Cols = Table.SelectColumns(Rows, {"captured_utc","game_date_et","commence_time_utc","away","home","book","market","outcome","point","price"})
in
    Cols
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
   'If a tab is empty, the file it reads has no rows yet (for example Results before the first game is played).',
   '',
   'Today: model projections vs the market (docs\daily\latest.csv, rewritten at 12:00 and 6:40 PM ET on game days).',
   'Odds: the latest odds snapshot, spreads and totals, every book (data\odds\odds_archive.csv).',
   'Injuries: latest Out / Doubtful statuses for games today and tomorrow (informational only; the model does not use them).',
   'Results: the 120 most recent 2026-27 team results (refreshed by the 6:30 AM task).',
   'Health: last data-collection health check (counts only).',
   '',
   'NOT A RECOMMENDATION. The v1 model failed its signed 2025-26 confirmation test and has no demonstrated edge (docs\Confirmation_Results.md).',
   '"Middle of market" is the median across books; with an even number of books it can fall between two posted numbers, so it may not be a line anyone offers. Use the range and the Bovada/DraftKings columns.',
   'Queries read absolute paths under: ' + $root + '. If the folder moves, edit the file paths in Data > Queries & Connections.'
  )
  for ($i=0; $i -lt $text.Count; $i++) { $readme.Cells.Item($i+1,1).Value2 = $text[$i] }
  $readme.Cells.Item(1,1).Font.Bold = $true; $readme.Cells.Item(1,1).Font.Size = 14
  $readme.Columns.Item(1).ColumnWidth = 150

  $sheetFor = @{ 'Today'='Today'; 'Odds'='Odds'; 'Injuries'='Injuries'; 'Results'='Results' }
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
