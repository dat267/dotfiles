function Get-Selection {
    <#
    .SYNOPSIS
        Provides an interactive terminal-based selection menu for objects.
    #>
    param(
        [Parameter(Mandatory, ValueFromPipeline)]
        [psobject[]]$Data,
        [Alias("Cols")]
        [string[]]$Columns
    )
    begin { $collectedData = [System.Collections.Generic.List[psobject]]::new() }
    process { foreach ($item in $Data) { $collectedData.Add($item) } }
    end {
        if ($collectedData.Count -eq 0) { return @() }
        $displayCols = if ($Columns) { $Columns } else {
            $collectedData[0].PSObject.Properties.Name | Where-Object { $_ -notmatch "json|payload|query" } | Select-Object -First 5
        }
        $lookupTable = @{}; $index = 1
        $formattedRows = foreach ($item in $collectedData) {
            $lookupTable[$index] = $item
            $row = [ordered]@{ "#" = $index++ }
            foreach ($col in $displayCols) { $row[$col] = $item.$col }
            [PSCustomObject]$row
        }
        $formattedRows | Format-Table -AutoSize | Out-String | Write-Host -ForegroundColor Cyan
        $selection = Read-Host "Select numbers (e.g. 1,3,5), a range (1-5), or 'all'"
        if ([string]::IsNullOrWhiteSpace($selection)) { return @() }
        $indices = if ($selection -eq 'all') { $lookupTable.Keys } else {
            $selection -split ',' | ForEach-Object {
                $part = $_.Trim()
                if ($part -match '^(\d+)-(\d+)$') { $matches[1]..$matches[2] } else { $part }
            }
        }
        foreach ($id in $indices) {
            if ([int]::TryParse($id, [ref]0) -and $lookupTable.ContainsKey([int]$id)) { $lookupTable[[int]$id] }
        }
    }
}

# --- Bash-equivalent utilities (extracted from user profile) ---

# ls variants
function global:ll  { Get-ChildItem -Force @args | Format-Table Mode, LastWriteTime, Length, Name -AutoSize }
function global:la  { Get-ChildItem -Force @args }
function global:l   { Get-ChildItem @args }

# head / tail
function global:head {
    param([int]$n = 10, [Parameter(ValueFromPipeline=$true, ValueFromRemainingArguments=$true)] $input)
    $input | Select-Object -First $n
}
function global:tail {
    param([int]$n = 10, [Parameter(ValueFromPipeline=$true, ValueFromRemainingArguments=$true)] $input)
    $input | Select-Object -Last $n
}

# wc
function global:wc {
    param([switch]$l, [switch]$w, [switch]$c, [Parameter(ValueFromPipeline=$true)] [string[]]$InputObject)
    begin { $lines = @() }; process { $lines += $InputObject }
    end {
        $text = $lines -join "`n"; $lineCount = $lines.Count
        $wordCount = ($text -split '\s+' | Where-Object { $_ }).Count; $charCount = $text.Length
        if ($l) { return $lineCount }; if ($w) { return $wordCount }; if ($c) { return $charCount }
        "$lineCount $wordCount $charCount"
    }
}

# cat
function global:cat {
    param([switch]$n, [Parameter(Position = 0, ValueFromRemainingArguments = $true)] [string[]]$Path)
    if ($Path) { foreach ($p in $Path) {
        if ($n) { $i = 1; foreach ($line in [System.IO.File]::ReadLines($p)) { "{0,6}`t{1}" -f $i++, $line } }
        else { Get-Content $p }
    } } else { $input | ForEach-Object { $_ } }
}

# realpath / basename / dirname
function global:realpath { param([string]$Path) (Resolve-Path $Path -ErrorAction SilentlyContinue).Path ?? [System.IO.Path]::GetFullPath($Path) }
function global:basename { param([string]$Path, [string]$Suffix) $b = [System.IO.Path]::GetFileName($Path); if ($Suffix -and $b.EndsWith($Suffix)) { $b = $b.Substring(0, $b.Length - $Suffix.Length) }; $b }
function global:dirname { param([string]$Path) [System.IO.Path]::GetDirectoryName((Resolve-Path $Path -ErrorAction SilentlyContinue).Path ?? $Path) }

# env / export
function global:env {
    param([string]$Name)
    if ($Name) { [System.Environment]::GetEnvironmentVariable($Name) }
    else { Get-ChildItem Env: | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" } }
}
function global:export { param([string]$Assignment) $k,$v = $Assignment -split '=',2; [System.Environment]::SetEnvironmentVariable($k.Trim(),$v); Set-Item -Path "Env:$($k.Trim())" -Value $v }

# source / man / time
function global:source { param([string]$Path) . $Path }
function global:man { param([string]$Command) Get-Help $Command -Full | Out-Host -Paging }
function global:time {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Cmd)
    $sw = [System.Diagnostics.Stopwatch]::StartNew(); & $Cmd[0] ($Cmd | Select-Object -Skip 1); $sw.Stop()
    Write-Host "`nreal`t$($sw.Elapsed.ToString('m\:ss\.fff'))" -ForegroundColor DarkGray
}

# kill / psg / pkill / pgrep
function global:kill { param([string]$Target, [int]$Signal = 15) if ($Target -match '^\d+$') { Stop-Process -Id ([int]$Target) -Force -ErrorAction SilentlyContinue } else { Stop-Process -Name $Target -Force -ErrorAction SilentlyContinue } }
function global:psg { param([string]$Name) if ($Name) { Get-Process | Where-Object { $_.Name -like "*$Name*" } } else { Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 } }
function global:pkill { param([string]$Name) Get-Process | Where-Object { $_.Name -like "*$Name*" } | Stop-Process -Force }
function global:pgrep { param([string]$Name) Get-Process | Where-Object { $_.Name -like "*$Name*" } | Select-Object Id, Name, CPU, WorkingSet | Format-Table -AutoSize }

# diff / hgrep
function global:diff { param([string]$File1, [string]$File2) if (Get-Command git -ErrorAction SilentlyContinue) { git diff --no-index -- $File1 $File2 } else { Compare-Object (Get-Content $File1) (Get-Content $File2) | ForEach-Object { ("< ", "> ")[$_.SideIndicator -eq '=>'] + $_.InputObject } } }
function global:hgrep { param([string]$Pattern) Get-History | Where-Object { $_.CommandLine -match $Pattern } | Select-Object Id, CommandLine | Format-Table -AutoSize }

# tee
function global:tee { param([string]$Path, [switch]$Append, [Parameter(ValueFromPipeline=$true)][object]$InputObject) process { $InputObject | Out-File -FilePath $Path -Append:$Append -Encoding utf8 -Width 9999; $InputObject } }

# md5 / sha256
function global:md5 { param([string]$Path) Get-FileHash $Path -Algorithm MD5 | Select-Object -Expand Hash }
function global:sha256 { param([string]$Path) Get-FileHash $Path -Algorithm SHA256 | Select-Object -Expand Hash }

# ports
function global:ports {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) { Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize }
    else { netstat -an | Select-String 'LISTEN' }
}

# du / df
function global:du { param([string]$Path = '.') Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | ForEach-Object { "{0:N2} MB  {1}" -f ($_.Sum / 1MB), (Resolve-Path $Path) } }
function global:df { Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='Used(GB)';E={[math]::Round(($_.Used/1GB),2)}},@{N='Free(GB)';E={[math]::Round(($_.Free/1GB),2)}},@{N='Total(GB)';E={[math]::Round((($_.Used+$_.Free)/1GB),2)}} | Format-Table -AutoSize }

# chmod / chown stubs
function global:chmod { Write-Warning "chmod is not supported on Windows. Use 'icacls' or 'Set-Acl' instead." }
function global:chown { Write-Warning "chown is not supported on Windows. Use 'icacls' or 'Set-Acl' instead." }

# ln
function global:ln { param([switch]$s, [string]$Target, [string]$Link) if ($s) { New-Item -ItemType SymbolicLink -Path $Link -Target $Target -Force | Out-Null } else { New-Item -ItemType HardLink -Path $Link -Target $Target -Force | Out-Null } }

# cp, mv, rm
function global:cp { param([switch]$r, [switch]$f, [string]$Source, [string]$Destination) $opts = @{Path=$Source;Destination=$Destination}; if ($r) { $opts['Recurse'] = $true }; if ($f) { $opts['Force'] = $true }; Copy-Item @opts }
function global:mv { param([string]$Source, [string]$Destination, [switch]$f) Move-Item -Path $Source -Destination $Destination -Force:$f }
function global:rm { param([switch]$r, [switch]$f, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Path) foreach ($p in $Path) { Remove-Item -Path $p -Recurse:$r -Force:$f -ErrorAction $(if ($f) {'SilentlyContinue'} else {'Continue'}) } }