# Drive PCSX2 for in-game checks.
#   pcsx2ctl.ps1 start <iso>          launch windowed (per-game settings still apply)
#   pcsx2ctl.ps1 keys "<seq>"         e.g. "Return:150,wait:2000,K:150,Down:120"; "+Q:300,E:100,E:100,-Q:0" holds Q while tapping E
#   pcsx2ctl.ps1 snap <out.png> [w]   capture the PCSX2 window client area, scaled to width w (default 1600)
#   pcsx2ctl.ps1 stop
param([string]$cmd, [string]$arg1, [string]$arg2)
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class Ctl {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static uint ForegroundPid() { uint pid; GetWindowThreadProcessId(GetForegroundWindow(), out pid); return pid; }
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint c, uint t);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public static void Focus(IntPtr h) {
    uint hp; GetWindowThreadProcessId(h, out hp);
    if (ForegroundPid() == hp) return;               // already focused: an Alt tap here would turn the next Return into Alt+Return (fullscreen)
    keybd_event(0x12, 0, 0, UIntPtr.Zero);          // Alt tap lets SetForegroundWindow succeed
    keybd_event(0x12, 0, 2, UIntPtr.Zero);
    ShowWindow(h, 9);
    SetForegroundWindow(h);
  }
  public static void Key(byte vk, bool up, bool ext) {
    byte sc = (byte)MapVirtualKey(vk, 0);
    keybd_event(vk, sc, (ext ? 1u : 0u) | (up ? 2u : 0u), UIntPtr.Zero);
  }
  public static int[] Client(IntPtr h) {
    RECT c; GetClientRect(h, out c);
    POINT p = new POINT(); ClientToScreen(h, ref p);
    return new int[] { p.X, p.Y, c.R - c.L, c.B - c.T };
  }
}
'@
Add-Type -AssemblyName System.Drawing
[Ctl]::SetProcessDPIAware() | Out-Null

function Get-Win {
  $p = Get-Process pcsx2-qt -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $p) { throw 'PCSX2 window not found' }
  $p.MainWindowHandle
}

# Keys must only ever reach PCSX2: refocus and verify the foreground process before every key.
function Assert-Focus {
  $p = Get-Process pcsx2-qt -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $p) { throw 'PCSX2 not running' }
  for ($i = 0; $i -lt 6; $i++) {
    if ([Ctl]::ForegroundPid() -eq [uint32]$p.Id) { return }
    [Ctl]::Focus($p.MainWindowHandle); Start-Sleep -Milliseconds 250
  }
  throw 'PCSX2 is not the foreground window; refusing to send keys'
}

$vk = @{ Return=0x0D; Escape=0x1B; Space=0x20; Backspace=0x08; Tab=0x09; Left=0x25; Up=0x26; Right=0x27; Down=0x28;
         F1=0x70; F2=0x71; F3=0x72; F8=0x77; Period=0xBE }
$ext = @('Left','Up','Right','Down')

switch ($cmd) {
  'start' {
    $exe = if ($env:PCSX2_EXE) { $env:PCSX2_EXE } else { 'C:\Games\PCSX2\pcsx2-qt.exe' }
    Start-Process $exe -ArgumentList '-nofullscreen', '--', "`"$arg1`"" | Out-Null
    for ($i = 0; $i -lt 30; $i++) { Start-Sleep 1; try { $h = Get-Win; break } catch {} }
    $h = Get-Win; [Ctl]::Focus($h); 'started'
  }
  'keys' {
    $h = Get-Win; [Ctl]::Focus($h); Start-Sleep -Milliseconds 300
    $held = @{}
    try {
    foreach ($step in $arg1.Split(',')) {
      $k, $ms = $step.Split(':'); $ms = [int]$ms
      if ($k -eq 'wait') { Start-Sleep -Milliseconds $ms; continue }
      if ($k -match '^[+-].') {   # +Q:ms presses Q and keeps it down, -Q:ms releases it (chords: hold L1, tap R1)
        $up = $k[0] -eq '-'; $k = $k.Substring(1)
        $code = if ($vk.ContainsKey($k)) { $vk[$k] } else { [byte][char]$k.ToUpper() }
        Assert-Focus
        [Ctl]::Key([byte]$code, $up, ($ext -contains $k))
        if ($up) { $held.Remove($k) } else { $held[$k] = $code }
        Start-Sleep -Milliseconds $ms
        continue
      }
      $alt = $k.StartsWith('Alt+'); if ($alt) { $k = $k.Substring(4) }   # e.g. Alt+Return toggles fullscreen
      $code = if ($vk.ContainsKey($k)) { $vk[$k] } else { [byte][char]$k.ToUpper() }
      $isExt = $ext -contains $k
      Assert-Focus
      if ($alt) { [Ctl]::Key(0x12, $false, $false) }
      [Ctl]::Key([byte]$code, $false, $isExt); Start-Sleep -Milliseconds $ms
      [Ctl]::Key([byte]$code, $true, $isExt); Start-Sleep -Milliseconds 120
      if ($alt) { [Ctl]::Key(0x12, $true, $false) }
    }
    } finally {   # never leave a key stuck down (focus loss or error mid-chord)
      foreach ($k in @($held.Keys)) { [Ctl]::Key([byte]$held[$k], $true, ($ext -contains $k)) }
    }
    'keys sent'
  }
  'snap' {
    $h = Get-Win; [Ctl]::Focus($h); Start-Sleep -Milliseconds 400
    $x, $y, $w, $hh = [Ctl]::Client($h)
    $bmp = [System.Drawing.Bitmap]::new($w, $hh)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($x, $y, 0, 0, [System.Drawing.Size]::new($w, $hh)); $g.Dispose()
    $ow = [Math]::Min($(if ($arg2) { [int]$arg2 } else { 1600 }), $w); $oh = [int]($hh * $ow / $w)
    $o = [System.Drawing.Bitmap]::new($ow, $oh)
    $g = [System.Drawing.Graphics]::FromImage($o)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($bmp, 0, 0, $ow, $oh); $g.Dispose()
    $o.Save($arg1, [System.Drawing.Imaging.ImageFormat]::Png); $o.Dispose(); $bmp.Dispose()
    "saved $arg1 (${w}x${hh} -> ${ow}x${oh})"
  }
  'stop' { Get-Process pcsx2-qt -ErrorAction SilentlyContinue | Stop-Process -Force; 'stopped' }
}
