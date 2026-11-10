<#
.SYNOPSIS
  Export HFSQL Classic tables (.fic) to XML with PC SOFT's WDMap, without the analysis (.wdd) and without
  anything appearing on screen.

.DESCRIPTION
  WDMap opens a .fic given on its command line and reads the file's own description, so its XML export carries
  the real column names even when the analysis is lost. This script starts WDMap on a separate, hidden Windows
  desktop and drives File > Export > "to an XML file" with posted window messages: no real keystrokes, no
  focus stealing, the user keeps working.

  - Never overwrites: a table whose <OutDir>\<Table>.XML exists is skipped (status SKIPPED_EXISTS), so an
    interrupted run can be resumed; if WDMap still asks to confirm an overwrite, the table fails.
  - One line per table in <OutDir>\_log_worker<N>.tsv: name, .fic bytes, status, rows, seconds.
    Status OK, SKIPPED_EXISTS, EMPTY_OR_NO_EXPORT (WDMap greys Export out on empty tables) or an error.
  - Failed tables have no XML: run the same command again to retry them. The first table of each worker
    can fail once with NO_MENU (startup timing on a fresh hidden desktop).
  - Work on a COPY of the data folder.

  See scripts/windows/README.md (WDMap export without the analysis) for how it works and its limits.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\wdmap_export.ps1 -DataDir C:\data -OutDir C:\migration\xml -Workers 4
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\wdmap_export.ps1 -DataDir C:\data -OutDir C:\migration\xml -Tables Customers,Orders
#>
param(
  [Parameter(Mandatory = $true)][string]$DataDir,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$WDMap = "",              # default: newest C:\PC SOFT\*\Programs\WDMAP.exe
  [int]$Workers = 1,                # parallel WDMap instances
  [int]$Worker = -1,                # internal: index of this worker (-1 = coordinator)
  [string[]]$Tables = @(),          # only these tables (base names, comma-separated or repeated)
  [int]$OpenTimeout = 900,          # seconds for WDMap to open a large .fic
  [int]$ExportTimeout = 3600        # seconds for one table's export
)
$ErrorActionPreference = "Stop"
$Tables = @($Tables | ForEach-Object { $_ -split ',' } | Where-Object { $_ })

if (-not $WDMap) {
  $found = @(Get-ChildItem "C:\PC SOFT\*\Programs\WDMAP.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)
  if (-not $found.Count) { throw "WDMAP.exe not found under C:\PC SOFT\*\Programs: pass -WDMap <path>" }
  $WDMap = $found[0].FullName
}
if (-not (Test-Path $WDMap)) { throw "WDMap not found: $WDMap" }
if (-not (Test-Path $DataDir)) { throw "Data folder not found: $DataDir" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path

# Coordinator: one child process per worker, each taking every N-th table.
if ($Worker -lt 0) {
  if ($Workers -le 1) { $Worker = 0; $Workers = 1 }
  else {
    Write-Host "WDMap: $WDMap - $Workers workers - logs in $OutDir\_log_worker*.tsv"
    $children = foreach ($w in 0..($Workers - 1)) {
      $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-DataDir", "`"$DataDir`"",
                   "-OutDir", "`"$OutDir`"", "-WDMap", "`"$WDMap`"", "-Workers", $Workers, "-Worker", $w,
                   "-OpenTimeout", $OpenTimeout, "-ExportTimeout", $ExportTimeout)
      if ($Tables.Count) { $argList += @("-Tables", ($Tables -join ',')) }
      Start-Process powershell -ArgumentList $argList -WindowStyle Hidden -PassThru
    }
    $children | Wait-Process
    return
  }
}

if (-not ('WDMapHidden' -as [type])) {
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class WDMapHidden {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct SI { public int cb; public string r; public string desk; public string title; public int x,y,w,h,xc,yc,fill,flags; public short show, r2; public IntPtr r3, i, o, e; }
  [StructLayout(LayoutKind.Sequential)] public struct PI { public IntPtr hp, ht; public int pid, tid; }
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr CreateDesktop(string n, IntPtr d, IntPtr dm, int f, uint acc, IntPtr sa);
  [DllImport("user32.dll")] public static extern bool CloseDesktop(IntPtr d);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool CreateProcess(string app, string cmd, IntPtr pa, IntPtr ta, bool inh, uint fl, IntPtr env, string dir, ref SI si, out PI pi);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumDesktopWindows(IntPtr d, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  public static IntPtr Desk;
  public static PI Start(string desk, string exe, string args) {
    if (Desk == IntPtr.Zero) Desk = CreateDesktop(desk, IntPtr.Zero, IntPtr.Zero, 0, 0x10000000, IntPtr.Zero);
    if (Desk == IntPtr.Zero) throw new Exception("CreateDesktop failed");
    SI si = new SI(); si.cb = Marshal.SizeOf(si); si.desk = desk; PI pi;
    if (!CreateProcess(exe, "\"" + exe + "\" " + args, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, null, ref si, out pi))
      throw new Exception("CreateProcess failed " + Marshal.GetLastWin32Error());
    CloseHandle(pi.ht); CloseHandle(pi.hp);
    return pi;
  }
  public class Win { public IntPtr H; public string Cls, Title; public bool Visible; }
  static Win Describe(IntPtr h) {
    var t = new StringBuilder(512); var c = new StringBuilder(256); GetWindowText(h, t, 512); GetClassName(h, c, 256);
    return new Win { H = h, Cls = c.ToString(), Title = t.ToString(), Visible = IsWindowVisible(h) };
  }
  // Top-level windows of a process on the hidden desktop.
  public static List<Win> Windows(int pid) {
    var l = new List<Win>();
    EnumDesktopWindows(Desk, (h, x) => { int p; GetWindowThreadProcessId(h, out p); if (p == pid) l.Add(Describe(h)); return true; }, IntPtr.Zero);
    return l;
  }
  public static IntPtr FindChild(IntPtr parent, string cls, int id) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(parent, (h, x) => { var c = new StringBuilder(256); GetClassName(h, c, 256); if (c.ToString() == cls && GetDlgCtrlID(h) == id) { found = h; return false; } return true; }, IntPtr.Zero);
    return found;
  }
}
"@
}

$WM_KEYDOWN = 0x100; $WM_KEYUP = 0x101; $WM_CHAR = 0x102; $WM_SYSKEYDOWN = 0x104; $WM_SYSKEYUP = 0x105
$EM_SETSEL = 0x00B1; $BM_CLICK = 0x00F5; $VK_DOWN = 0x28; $VK_RETURN = 0x0D

function Post($h, $msg, $w, $l) { [void][WDMapHidden]::PostMessage($h, $msg, [IntPtr]$w, [IntPtr]$l); Start-Sleep -Milliseconds 300 }
function Key($h, $vk) { Post $h $WM_KEYDOWN $vk 1; Post $h $WM_KEYUP $vk 0xC0000001 }
function Visible($procId) { @([WDMapHidden]::Windows($procId) | Where-Object { $_.Visible }) }
function Top($procId, $pattern) { Visible $procId | Where-Object { $_.Title -like $pattern } | Select-Object -First 1 }
# WinDev menus and popup lists are untitled top-level "WinDevObject" windows.
function Popups($procId) { Visible $procId | Where-Object { $_.Cls -eq 'WinDevObject' -and $_.Title -eq '' } | ForEach-Object { $_.H } }
function WaitFor([scriptblock]$cond, [double]$sec) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $sec) { $r = & $cond; if ($r) { return $r }; Start-Sleep -Milliseconds 250 }
  return $null
}

$log = Join-Path $OutDir "_log_worker$Worker.tsv"
$files = @(Get-ChildItem $DataDir -Filter *.fic | Sort-Object Name)
if ($Tables.Count) { $files = @($files | Where-Object { $Tables -contains $_.BaseName }) }
$i = -1
foreach ($f in $files) {
  $i++; if ($i % $Workers -ne $Worker) { continue }
  $name = $f.BaseName; $base = Join-Path $OutDir $name; $xml = "$base.XML"
  $t0 = Get-Date; $status = "?"; $procId = 0
  if (Test-Path $xml) { $status = "SKIPPED_EXISTS" }
  else {
    try {
      $proc = [WDMapHidden]::Start("WDMapExport", $WDMap, "`"$($f.FullName)`""); $procId = $proc.pid
      $main = WaitFor { Top $procId "WDMap - *" } $OpenTimeout
      if (-not $main) { throw "OPEN_TIMEOUT: " + ((Visible $procId | ForEach-Object { "$($_.Cls) '$($_.Title)'" }) -join ' ; ') }
      Start-Sleep -Milliseconds 700
      $before = @(Popups $procId)
      Post $main.H $WM_SYSKEYDOWN 0x46 0x20210001; Post $main.H $WM_SYSKEYUP 0x46 0xE0210001          # Alt+F: File menu
      $p1 = WaitFor { $n = @(Popups $procId | Where-Object { $before -notcontains $_ }); if ($n.Count) { ,$n } } 5
      if (-not $p1) { throw "NO_MENU" }
      foreach ($h in $p1) { Key $h 0x45 }                                                              # E: Export
      $p2 = WaitFor { $n = @(Popups $procId | Where-Object { $before -notcontains $_ -and $p1 -notcontains $_ }); if ($n.Count) { ,$n } } 5
      $target = if ($p2) { $p2 } else { $p1 }
      foreach ($h in $target) { Key $h $VK_DOWN; Key $h $VK_DOWN; Key $h $VK_RETURN }                  # third entry: to an XML file
      $dlg = WaitFor { Top $procId "Select *" } 6
      if (-not $dlg) { throw "EMPTY_OR_NO_EXPORT" }                                                    # Export is greyed out on empty tables
      $edit = [WDMapHidden]::FindChild($dlg.H, "Edit", 1001)
      $btn = [WDMapHidden]::FindChild($dlg.H, "Button", 1)
      if ($edit -eq [IntPtr]::Zero -or $btn -eq [IntPtr]::Zero) { throw "SAVE_DIALOG_CHANGED" }
      # The file-name field ignores WM_SETTEXT: select all, erase, then type the path with WM_CHAR.
      [void][WDMapHidden]::SendMessage($edit, $EM_SETSEL, [IntPtr]0, [IntPtr](-1))
      [void][WDMapHidden]::SendMessage($edit, $WM_CHAR, [IntPtr]8, [IntPtr]1)
      foreach ($ch in $base.ToCharArray()) { [void][WDMapHidden]::SendMessage($edit, $WM_CHAR, [IntPtr][int]$ch, [IntPtr]1) }
      Post $btn $BM_CLICK 0 0                                                                          # Save
      # Done when WDMap shows its confirmation: a second "WDMap - <table>" window.
      $done = WaitFor {
        if (Top $procId "Confirm*") { "CONFIRM" }
        elseif (@(Visible $procId | Where-Object { $_.Title -like 'WDMap - *' }).Count -ge 2) { "OK" }
      } $ExportTimeout
      if ($done -eq "CONFIRM") { throw "CONFIRM_OVERWRITE (not overwritten)" }
      if (-not $done) { throw "EXPORT_TIMEOUT" }
      $status = "OK"
    } catch { $status = "$($_.Exception.Message)" -replace "[`t`r`n]+", " " }
    finally { if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } }
  }
  $rows = 0  # one <Table> element per row, alone on its line
  if (Test-Path $xml) { $rows = @(Select-String -Path $xml -Pattern "^\s*<$([regex]::Escape($name))>\s*$").Count }
  "$name`t$($f.Length)`t$status`t$rows`t$([int]((Get-Date) - $t0).TotalSeconds)" | Out-File -Append -Encoding utf8 $log
}
if ([WDMapHidden]::Desk -ne [IntPtr]::Zero) { [void][WDMapHidden]::CloseDesktop([WDMapHidden]::Desk) }
"DONE" | Out-File -Append -Encoding utf8 $log
