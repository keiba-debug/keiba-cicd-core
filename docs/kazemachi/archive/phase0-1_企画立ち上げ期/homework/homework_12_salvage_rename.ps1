[CmdletBinding()]
param(
    [string]$TargetDir = (Get-Location).Path,
    [string]$MapPath = "",
    [switch]$Apply
)

if ([string]::IsNullOrWhiteSpace($MapPath)) {
    $MapPath = Join-Path $PSScriptRoot "homework_12_salvage_rename_map.csv"
}

if (-not (Test-Path -LiteralPath $TargetDir)) {
    throw "Target directory not found: $TargetDir"
}

if (-not (Test-Path -LiteralPath $MapPath)) {
    throw "Map file not found: $MapPath"
}

$rows = Get-Content -LiteralPath $MapPath -Encoding UTF8 | ConvertFrom-Csv

$plan = foreach ($row in $rows) {
    $oldName = [string]$row.OldFileName
    $newName = [string]$row.NewFileName
    $bucket = [string]$row.Bucket

    if ([string]::IsNullOrWhiteSpace($oldName) -or [string]::IsNullOrWhiteSpace($newName)) {
        continue
    }

    $oldPath = Join-Path $TargetDir $oldName
    $newPath = Join-Path $TargetDir $newName

    if (-not (Test-Path -LiteralPath $oldPath)) {
        [pscustomobject]@{ Old=$oldName; New=$newName; Bucket=$bucket; Status="MissingOld" }
        continue
    }
    if (Test-Path -LiteralPath $newPath) {
        [pscustomobject]@{ Old=$oldName; New=$newName; Bucket=$bucket; Status="ExistsNew" }
        continue
    }

    [pscustomobject]@{ Old=$oldName; New=$newName; Bucket=$bucket; Status="OK" }
}

Write-Output "=== Preview plan (TargetDir: $TargetDir) ==="
$plan | Sort-Object Old | ForEach-Object {
    if ($_.Status -eq "OK") {
        Write-Output ("OK: " + $_.Old + " -> " + $_.New + " [" + $_.Bucket + "]")
    } else {
        Write-Output ($_.Status + ": " + $_.Old + " -> " + $_.New + " [" + $_.Bucket + "]")
    }
}

$toApply = $plan | Where-Object { $_.Status -eq "OK" }

if ($Apply) {
    foreach ($item in $toApply) {
        Rename-Item -LiteralPath (Join-Path $TargetDir $item.Old) -NewName $item.New -Force
    }
    Write-Output ("Applied renames: " + $toApply.Count)
} else {
    Write-Output ("Apply switch not set. Renames not executed. OK count: " + $toApply.Count)
}

