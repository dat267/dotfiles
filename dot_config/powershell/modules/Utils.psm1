
function Invoke-RedashQuery {
    <#
    .SYNOPSIS
        Acts as a transient database client via the Redash REST API.

    .DESCRIPTION
        Updates an existing Redash query with a new SQL string, executes it, polls for the result, 
        and returns the data as PowerShell objects. Wipes the query text upon completion.

    .PARAMETER RedashUrl
        The base URL of your Redash instance (e.g., http://localhost:5000).

    .PARAMETER ApiKey
        The User API Key found in Redash profile settings.

    .PARAMETER PlaceholderQueryId
        The ID of the placeholder query to be used for the execution.

    .PARAMETER DataSourceId
        The ID of the target database connection in Redash.

    .PARAMETER QueryString
        The SQL query string to execute.

    .PARAMETER TimeoutSeconds
        Optional. Max time to wait for the query to finish. Set to 0 for no timeout. Defaults to 0.

    .EXAMPLE
        Invoke-RedashQuery -RedashUrl "http://localhost:5000" -ApiKey "..." -PlaceholderQueryId 1 -DataSourceId 1 -QueryString "SELECT * FROM users"
    #>

    [CmdletBinding()]
    param (
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$RedashUrl,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ApiKey,
        [Parameter(Mandatory)] [int]$PlaceholderQueryId,
        [Parameter(Mandatory)] [int]$DataSourceId,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$QueryString,
        [Parameter()] [int]$TimeoutSeconds = 0
    )

    $ErrorActionPreference = 'Stop'
    $BaseUrl = $RedashUrl.TrimEnd('/')
    $ResultId = $null
    
    $Headers = @{ 
        "Authorization" = "Key $ApiKey"
        "Content-Type"  = "application/json; charset=utf-8"
    }
    
    try {
        $UpdateBody = @{ query = $QueryString; data_source_id = $DataSourceId; max_age = 0 } | ConvertTo-Json -Depth 10
        $Payload = [System.Text.Encoding]::UTF8.GetBytes($UpdateBody)

        Invoke-RestMethod -Uri "$BaseUrl/api/queries/$PlaceholderQueryId" -Method Post -Headers $Headers -Body $Payload | Out-Null
        
        $Response = Invoke-RestMethod -Uri "$BaseUrl/api/queries/$PlaceholderQueryId/results" -Method Post -Headers $Headers -Body $Payload

        if ($Response.query_result.id) {
            $ResultId = $Response.query_result.id
        }
        elseif ($Response.job.id) {
            $JobId = $Response.job.id
            $StartTime = Get-Date
            
            while ($true) {
                if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $StartTime).TotalSeconds -gt $TimeoutSeconds) {
                    throw "Timeout: Redash query did not complete within $TimeoutSeconds seconds."
                }

                $Status = Invoke-RestMethod -Uri "$BaseUrl/api/jobs/$JobId" -Method Get -Headers $Headers
                
                if ($Status.job.status -eq 3) {
                    $ResultId = $Status.job.query_result_id
                    break
                }

                if ($Status.job.status -eq 4) {
                    throw "Redash Task Failed: $($Status.job.error)"
                }

                Start-Sleep -Seconds 1
            }
        }
        else {
            throw "Unexpected response from Redash. No Job ID or Result ID found."
        }

        if ($null -ne $ResultId) {
            $FinalData = Invoke-RestMethod -Uri "$BaseUrl/api/queries/$PlaceholderQueryId/results/$ResultId.json" -Method Get -Headers $Headers
            return $FinalData.query_result.data.rows | ForEach-Object { [PSCustomObject]$_ }
        }
    }
    catch {
        Write-Error "Invoke-RedashQuery Error: $($_.Exception.Message)"
        throw $_
    }
    finally {
        $CleanupBody = @{ query = ""; data_source_id = $DataSourceId } | ConvertTo-Json
        $CleanupPayload = [System.Text.Encoding]::UTF8.GetBytes($CleanupBody)
        
        Invoke-RestMethod -Uri "$BaseUrl/api/queries/$PlaceholderQueryId" -Method Post -Headers $Headers -Body $CleanupPayload -ErrorAction SilentlyContinue | Out-Null
    }
}

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