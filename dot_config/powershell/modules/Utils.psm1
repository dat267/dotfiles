function Get-Selection {
    <#
    .SYNOPSIS
        Provides an interactive terminal-based selection menu for objects.
    .DESCRIPTION
        Takes input objects via the pipeline or parameter, displays them in a Cyan-formatted table with index numbers, 
        and prompts the user to select specific items. Supports individual numbers, comma-separated lists, ranges, or 'all'.
    .PARAMETER Data
        The collection of objects to be displayed for selection. Supports pipeline input.
    .PARAMETER Columns
        Specific property names to display in the selection table. If omitted, defaults to the first 5 properties 
        excluding common metadata fields (json, payload, query).
    .EXAMPLE
        Get-Process | Get-Selection -Columns Name, Id, CPU
    #>
    param(
        [Parameter(Mandatory, ValueFromPipeline)]
        [psobject[]]$Data,

        [Alias("Cols")]
        [string[]]$Columns
    )

    begin {
        $collectedData = [System.Collections.Generic.List[psobject]]::new()
    }

    process {
        foreach ($item in $Data) {
            $collectedData.Add($item)
        }
    }

    end {
        if ($collectedData.Count -eq 0) { return @() }

        $displayCols = if ($Columns) {
            $Columns
        }
        else {
            $collectedData[0].PSObject.Properties.Name | 
            Where-Object { $_ -notmatch "json|payload|query" } | 
            Select-Object -First 5
        }

        $lookupTable = @{}
        $index = 1
        $formattedRows = foreach ($item in $collectedData) {
            $lookupTable[$index] = $item
            $row = [ordered]@{ "#" = $index++ }
            foreach ($col in $displayCols) { 
                $row[$col] = $item.$col 
            }
            [PSCustomObject]$row
        }

        $formattedRows | Format-Table -AutoSize | Out-String | Write-Host -ForegroundColor Cyan

        $selection = Read-Host "Select numbers (e.g. 1,3,5), a range (1-5), or 'all'"
        if ([string]::IsNullOrWhiteSpace($selection)) { return @() }

        $indices = if ($selection -eq 'all') {
            $lookupTable.Keys
        }
        else {
            $selection -split ',' | ForEach-Object {
                $part = $_.Trim()
                if ($part -match '^(\d+)-(\d+)$') { 
                    $matches[1]..$matches[2] 
                } 
                else { 
                    $part 
                }
            }
        }

        foreach ($id in $indices) {
            if ([int]::TryParse($id, [ref]0) -and $lookupTable.ContainsKey([int]$id)) {
                $lookupTable[[int]$id]
            }
        }
    }
}