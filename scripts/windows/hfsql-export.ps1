# HFSQL Classic export through the driver's ANSI ODBC entry points (HfSqlOdbcAnsi.cs), for when export_odbc.py
# crashes (exit code 139 / access violation while connecting: the HFSQL 28 driver's Unicode entry points).
# Run it in the 32-bit Windows PowerShell; the HFSQL ODBC driver tested is 32-bit:
#
#   C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass `
#     -File scripts\windows\hfsql-export.ps1 -Source <data folder> -Analysis <app>.wdd -Work <new folder>
#
#   -Source    folder with the legacy .fic/.ndx/.mmo/.ftx files (never written: every file is copied first, hash-checked)
#   -Analysis  the legacy .wdd analysis file
#   -Work      NEW folder for this run: receives source\ (the copy) and jsonl\ (one <table>.jsonl per .fic)
#   -Driver    optional path of the HFSQL ODBC driver DLL (default: the registered "HFSQL" driver, else HFSQL 28's path)
#   -CodePage  optional ANSI code page of the data (default 1252, Western European Windows)
#
# A temporary per-user DSN points the driver at the copy; it is always deleted afterwards. Then convert the JSONL to
# data.sqlite + CSV + manifest.json (the format of export_odbc.py) with hfsql_jsonl.py.
# Output for a calling program: "STEP <name>" lines, one "<table>: <n> rows ..." line per table, and on failure a single
# "ERROR <message>" line with exit code 1.
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Analysis,
    [Parameter(Mandatory = $true)][string]$Work,
    [string]$Driver,
    [int]$CodePage = 1252
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
trap { Write-Output ("ERROR " + ($_.Exception.Message -replace '\s+', ' ')); exit 1 }
if ([IntPtr]::Size -ne 4) { throw 'Run this script in the 32-bit Windows PowerShell (C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe).' }

$sourcePath = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
$analysisPath = (Resolve-Path -LiteralPath $Analysis).Path
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Data folder not found: $sourcePath" }
if (-not (Test-Path -LiteralPath $analysisPath -PathType Leaf) -or $analysisPath -notmatch '\.wdd$') { throw "Not a .wdd analysis file: $analysisPath" }
if (Test-Path -LiteralPath $Work) { throw "The work folder already exists (use a new one per run): $Work" }
$workPath = [IO.Path]::GetFullPath($Work).TrimEnd('\')
if ($workPath.StartsWith($sourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'The work folder cannot be inside the data folder.' }

# Driver: explicit, else the registered HFSQL driver (a 32-bit host reads the 32-bit registry view), else HFSQL 28's default path.
if (-not $Driver) {
    try { $Driver = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\ODBC\ODBCINST.INI\HFSQL' -ErrorAction Stop).Driver } catch { }
}
if (-not $Driver) { $Driver = 'C:\Program Files (x86)\Common Files\PC SOFT\28.0\ODBC\Win32x86\wd280hfo.dll' }
if (-not (Test-Path -LiteralPath $Driver -PathType Leaf) -or [IO.Path]::GetFileName($Driver) -notmatch '^wd\d+hfo\.dll$') {
    throw "The 32-bit HFSQL ODBC driver (wd<version>hfo.dll) was not found: $Driver. Install PC SOFT's HFSQL ODBC driver or pass -Driver."
}

function Get-Sha256([string]$File) { (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash }

# 1. Copy (top-level data files only; links are refused), each file hash-checked, then the source re-checked.
$files = @(Get-ChildItem -LiteralPath $sourcePath -File -Force | Where-Object { $_.Extension -match '^\.(fic|ndx|mmo|ftx)$' } | Sort-Object Name)
if (@($files | Where-Object { $_.Extension -ieq '.fic' }).Count -eq 0) { throw 'The data folder holds no .fic file.' }
foreach ($file in $files) { if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Symbolic link refused: $($file.Name)" } }
$copyData = Join-Path $workPath 'source\data'
$copyAnalysis = Join-Path $workPath 'source\analysis.wdd'
$jsonl = Join-Path $workPath 'jsonl'
New-Item -ItemType Directory -Path $copyData -Force | Out-Null
Write-Output "STEP copy $($files.Count)"
$hashes = @{}
$analysisHash = Get-Sha256 $analysisPath
Copy-Item -LiteralPath $analysisPath -Destination $copyAnalysis
if ((Get-Sha256 $copyAnalysis) -ne $analysisHash) { throw 'The copy of the .wdd analysis does not match its source.' }
foreach ($file in $files) {
    $hash = Get-Sha256 $file.FullName
    $target = Join-Path $copyData $file.Name
    Copy-Item -LiteralPath $file.FullName -Destination $target
    if ((Get-Sha256 $target) -ne $hash) { throw "The copy of $($file.Name) does not match its source." }
    $hashes[$file.Name] = $hash
}
foreach ($file in $files) { if ((Get-Sha256 $file.FullName) -ne $hashes[$file.Name]) { throw "$($file.Name) changed during the copy. Close the legacy application and try again." } }
if ((Get-Sha256 $analysisPath) -ne $analysisHash) { throw 'The .wdd analysis changed during the copy.' }

# 2. Export through a temporary per-user DSN on the copy (always deleted).
Write-Output 'STEP export'
$dsn = 'MIGEXP' + ([guid]::NewGuid().ToString('N').Substring(0, 20))
$base = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Software\ODBC\ODBC.INI')
$sources = $base.CreateSubKey('ODBC Data Sources')
$created = $false
try {
    if ($null -ne $base.OpenSubKey($dsn)) { throw 'The temporary DSN already exists.' }
    $key = $base.CreateSubKey($dsn); $created = $true
    try {
        foreach ($pair in @(@('Driver', $Driver), @('RepFic', $copyData), @('Analyse', $copyAnalysis), @('Database', ''), @('Server Name', ''), @('Server Port', ''), @('IntegrityCheck', '0'))) {
            $key.SetValue($pair[0], $pair[1], [Microsoft.Win32.RegistryValueKind]::String)
        }
    } finally { $key.Dispose() }
    $sources.SetValue($dsn, 'HFSQL', [Microsoft.Win32.RegistryValueKind]::String)
    Add-Type -Path (Join-Path $PSScriptRoot 'HfSqlOdbcAnsi.cs') -ReferencedAssemblies System.Web.Extensions
    $names = @($files | Where-Object { $_.Extension -ieq '.fic' } | ForEach-Object { $_.BaseName })
    $connection = New-Object HfSqlOdbcAnsi($dsn, $CodePage)
    try { $connection.Export([string[]]$names, $jsonl) } finally { $connection.Dispose() }
} finally {
    if ($created) { $sources.DeleteValue($dsn, $false); $base.DeleteSubKeyTree($dsn, $false) }
    $sources.Dispose(); $base.Dispose()
}
foreach ($file in $files) { if ((Get-Sha256 $file.FullName) -ne $hashes[$file.Name]) { throw "The original $($file.Name) changed during the export." } }
Write-Output 'STEP done'
