# Design: Remove all PowerShell 5 support

Date: 2026-08-15
Status: Approved

## Goal

Remove all Windows PowerShell 5.x (PS5) support from the repo. The PowerShell
profile, junction script, and related tooling become PowerShell 7+ only.

## Background

- PS5 lacks the automatic platform variables (`$IsWindows`, `$IsLinux`,
  `$IsMacOS`), so the profile carries a compatibility shim that defines them
  as globals.
- The junction script wires a PS5 profile stub
  (`$docsDir\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`) into the
  `$profiles` array so Windows PowerShell 5 sources the shared profile.
- `dot_local/scripts/ps1/executable_MonitorNotifications.ps1` **requires**
  PS5: it relaunches itself into `powershell.exe` (5.1) because PowerShell 7
  lacks native WinRT projections. With PS5 dropped, this script cannot work.
- Design specs from 2026-08-15 claim "PS5/PS7 parity" and are now inaccurate.

## Changes

### Deleted

- `dot_local/scripts/ps1/executable_MonitorNotifications.ps1` — requires PS5
  (WinRT); delete.

### Modified

- `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1` —
  remove the PS5 compatibility shim (the `if ($null -eq $IsWindows)` block,
  lines ~5-11, defining `$IsWindows`/`$IsLinux`/`$IsMacOS`). The profile now
  uses the PS7 automatic variables directly.
- `run_onchange_after_create-junctions.ps1.tmpl` — remove
  `"$docsDir\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"` from the
  `$profiles` array (PS7-only stub remains).
- `docs/superpowers/specs/2026-08-15-windows-proxy-credentials-design.md` —
  update "PS 5.1 and PowerShell 7+" claims to PowerShell 7+ only.
- `docs/superpowers/specs/2026-08-15-windows-scoop-proxy-design.md` —
  same: state PS7-only, and remove the PS5 profile-path references.

## Edge cases

- The PS5 profile stub already deployed on machines
  (`$docsDir\WindowsPowerShell\...`) is not removed by chezmoi (it was written
  by the junction script, not chezmoi-managed). It becomes an inert orphan;
  the user may delete it manually.
- Historical plan documents (`docs/superpowers/plans/2026-08-15-*`) and the
  proxy test harness comments that mention PS5 are left as-is (historical
  records / gitignored scratch).

## Verification

- `grep -rn "WindowsPowerShell"` in tracked source returns nothing (outside
  docs history).
- Profile AST-parses (pwsh 7 harness).
- Junction script AST-parses.
- Proxy + scoop test harnesses still pass (they run on pwsh 7).

## Files touched

- Delete: `dot_local/scripts/ps1/executable_MonitorNotifications.ps1`
- Modify: `dot_config/powershell/executable_Microsoft.PowerShell_profile.ps1`,
  `run_onchange_after_create-junctions.ps1.tmpl`,
  `docs/superpowers/specs/2026-08-15-windows-proxy-credentials-design.md`,
  `docs/superpowers/specs/2026-08-15-windows-scoop-proxy-design.md`
