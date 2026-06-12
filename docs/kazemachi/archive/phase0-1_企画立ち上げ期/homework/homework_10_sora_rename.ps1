[CmdletBinding()]
param(
    [string]$TargetDir = (Get-Location).Path,
    [string]$MapPath = "",
    [switch]$Apply
)

if ([string]::IsNullOrWhiteSpace($MapPath)) {
    $MapPath = Join-Path $PSScriptRoot "homework_10_sora_rename_map.csv"
}

if (-not (Test-Path -LiteralPath $TargetDir)) {
    throw "Target directory not found: $TargetDir"
}

if (-not (Test-Path -LiteralPath $MapPath)) {
    throw "Rename map not found: $MapPath"
}

$rows = Get-Content -LiteralPath $MapPath -Encoding UTF8 | ConvertFrom-Csv

$duplicateTargets = $rows | Group-Object new_name | Where-Object { $_.Count -gt 1 }
if ($duplicateTargets) {
    throw "Duplicate target names found in rename map."
}

Write-Host ""
Write-Host "Target directory:" $TargetDir
Write-Host "Rename map:" $MapPath
Write-Host "Mode:" ($(if ($Apply) { "APPLY" } else { "PREVIEW" }))
Write-Host ""

foreach ($row in $rows) {
    $oldPath = Join-Path $TargetDir $row.old_name
    $newPath = Join-Path $TargetDir $row.new_name

    if (-not (Test-Path -LiteralPath $oldPath)) {
        Write-Warning ("Missing source file: " + $row.old_name)
        continue
    }

    if ((Test-Path -LiteralPath $newPath) -and ($row.old_name -ne $row.new_name)) {
        Write-Warning ("Target already exists: " + $row.new_name)
        continue
    }

    if ($Apply) {
        Rename-Item -LiteralPath $oldPath -NewName $row.new_name
        Write-Host ("RENAMED  " + $row.old_name + " -> " + $row.new_name)
    } else {
        Write-Host ("PREVIEW  " + $row.old_name + " -> " + $row.new_name + " [" + $row.quality + "]")
    }
}

Write-Host ""
if ($Apply) {
    Write-Host "Rename complete."
} else {
    Write-Host "Preview complete. Re-run with -Apply to rename files."
}
