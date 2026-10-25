# DataForge 360 - Portable Power BI data-source bootstrap.
# Run once AFTER extracting the complete ZIP and BEFORE opening project.pbip.
# It changes only the four CSV paths in this extracted project's local .tmdl files.

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelTableDirectory = [System.IO.Path]::Combine($projectDirectory, 'project.SemanticModel', 'definition', 'tables')
$dataDirectory = [System.IO.Path]::Combine($projectDirectory, 'data')
$snapshotSuffix = '2026-09-01_2026-09-05.csv'
$tables = @('daily', 'agency', 'borough', 'complaint')

foreach ($table in $tables) {
    $tmdlPath = [System.IO.Path]::Combine($modelTableDirectory, ($table + '.tmdl'))
    $csvName = 'dataforge_' + $table + '_' + $snapshotSuffix
    $csvPath = [System.IO.Path]::Combine($dataDirectory, $csvName)

    if (-not (Test-Path -LiteralPath $tmdlPath -PathType Leaf)) {
        throw "Missing semantic-model table: $tmdlPath"
    }
    if (-not (Test-Path -LiteralPath $csvPath -PathType Leaf)) {
        throw "Missing included data file: $csvPath"
    }

    $csvAbsolutePath = (Resolve-Path -LiteralPath $csvPath).ProviderPath
    # Power Query's M language doubles double quotes inside text literals.
    $mSafePath = $csvAbsolutePath.Replace('"', '""')
    $oldSource = [System.IO.File]::ReadAllText($tmdlPath)
    $pattern = 'File\.Contents\("[^"\r\n]*' + [regex]::Escape($csvName) + '"\)'

    if (-not [regex]::IsMatch($oldSource, $pattern)) {
        throw "Could not locate the existing $table CSV source. No changes made to this table."
    }

    $replacement = 'File.Contents("' + $mSafePath + '")'
    $updated = [regex]::Replace(
        $oldSource,
        $pattern,
        [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement }
    )
    if ($updated -eq $oldSource) {
        Write-Host "Already configured: $csvName"
    } else {
        [System.IO.File]::WriteAllText(
            $tmdlPath, $updated, [System.Text.UTF8Encoding]::new($false)
        )
        Write-Host "Configured: $csvName"
    }
}

Write-Host 'CSV paths configured. Open project.pbip in Power BI Desktop and use Refresh.'
