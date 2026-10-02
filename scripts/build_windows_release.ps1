param([string]$Version = '0.4.0')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $commonGit = (& git -C $project rev-parse --path-format=absolute --git-common-dir).Trim()
    $python = Join-Path (Split-Path $commonGit -Parent) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python virtual environment was not found.'
}
if ($Version -ne '0.4.0') {
    throw 'Version metadata currently supports only v0.4.0.'
}

function Invoke-Checked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "A required build step failed with exit code $LASTEXITCODE."
    }
}

function Clear-GeneratedDirectory([string]$path) {
    $resolvedProject = [IO.Path]::GetFullPath($project) + [IO.Path]::DirectorySeparatorChar
    $resolved = [IO.Path]::GetFullPath($path)
    if (-not $resolved.StartsWith($resolvedProject, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear unexpected path: $resolved"
    }
    if ([IO.Directory]::Exists($resolved)) {
        Get-ChildItem -LiteralPath $resolved -Recurse -Force | ForEach-Object {
            $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
        }
        [IO.Directory]::Delete($resolved, $true)
    }
}

Push-Location $project
try {
    Invoke-Checked $python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    Invoke-Checked $python @('scripts\fetch_tailcat.py')
    Clear-GeneratedDirectory (Join-Path $project 'build')
    Clear-GeneratedDirectory (Join-Path $project 'dist')
    Invoke-Checked $python @('-m', 'PyInstaller', '--noconfirm', '--clean', 'VoiceInput2PCReceiver.spec')

    $bundle = Join-Path $project 'dist\VoiceInput2PCReceiver'
    $exe = Join-Path $bundle 'VoiceInput2PCReceiver.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        throw 'Expected Windows executable was not produced.'
    }
    $versionInfo = (Get-Item -LiteralPath $exe).VersionInfo
    if ($versionInfo.FileVersion -ne '0.4.0.0' -or $versionInfo.ProductVersion -ne '0.4.0') {
        throw "Unexpected executable version metadata: $($versionInfo.FileVersion) / $($versionInfo.ProductVersion)"
    }
    $releaseRoot = (Resolve-Path (Join-Path $project 'release')).Path
    $output = Join-Path $releaseRoot ('output\windows-v' + $Version)
    $resolvedOutput = [IO.Path]::GetFullPath($output)
    if (-not $resolvedOutput.StartsWith($releaseRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected release output path: $resolvedOutput"
    }
    Clear-GeneratedDirectory $resolvedOutput
    [IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

    $packageName = 'VoiceInput2PC-Windows-v' + $Version + '.zip'
    $packagePath = Join-Path $resolvedOutput $packageName
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ('VoiceInput2PC-windows-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($temporary) | Out-Null
    try {
        foreach ($item in (Get-ChildItem -LiteralPath $bundle -Force)) {
            Copy-Item -LiteralPath $item.FullName -Destination $temporary -Recurse
        }
        $tailcatExe = Join-Path $project 'vendor\tailcat\windows\tailcat.exe'
        if (-not (Test-Path -LiteralPath $tailcatExe)) { throw 'Tailcat Windows sidecar is missing.' }
        Copy-Item -LiteralPath $tailcatExe -Destination (Join-Path $temporary 'tailcat.exe')
        Copy-Item -LiteralPath (Join-Path $project 'release\使用说明.txt') -Destination $temporary
        $inputs = @(Get-ChildItem -LiteralPath $temporary -Force | ForEach-Object FullName)
        Compress-Archive -LiteralPath $inputs -DestinationPath $packagePath -CompressionLevel Optimal
    } finally {
        $resolvedTemporary = [IO.Path]::GetFullPath($temporary)
        $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if ($resolvedTemporary.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Directory]::Exists($resolvedTemporary)) {
            [IO.Directory]::Delete($resolvedTemporary, $true)
        }
    }

    # Tcl 8.6.15 rejects library scripts from directories with permissive
    # system-temp ACLs on managed Windows machines. Verify in the repository's
    # generated build area, which matches a normal user extraction directory.
    $verification = Join-Path $project ('build\package-check-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($verification) | Out-Null
    try {
        Expand-Archive -LiteralPath $packagePath -DestinationPath $verification
        $packagedExe = Join-Path $verification 'VoiceInput2PCReceiver.exe'
        $packagedTcl = Join-Path $verification '_internal\_tcl_data\init.tcl'
        $packagedInstructions = Join-Path $verification '使用说明.txt'
        $packagedTailcat = Join-Path $verification 'tailcat.exe'
        foreach ($required in @($packagedExe, $packagedTcl, $packagedInstructions, $packagedTailcat)) {
            if (-not (Test-Path -LiteralPath $required)) {
                throw "Packaged Windows archive is missing: $required"
            }
        }
        $privateFiles = @(Get-ChildItem -LiteralPath $verification -Recurse -File | Where-Object {
            $_.Name -in @('pairing.json', 'config.json', 'cert.pem', 'key.pem', 'messages.db')
        })
        if ($privateFiles.Count -gt 0) {
            throw ('Packaged Windows archive contains private runtime files: ' +
                (($privateFiles | ForEach-Object FullName) -join ', '))
        }
        Invoke-Checked $python @('scripts\verify_first_run_ui.py', $packagedExe)
        Invoke-Checked $python @('scripts\verify_receiver_runtime.py', $packagedExe)
    } finally {
        $resolvedVerification = [IO.Path]::GetFullPath($verification)
        $generatedRoot = [IO.Path]::GetFullPath((Join-Path $project 'build')) + [IO.Path]::DirectorySeparatorChar
        if ($resolvedVerification.StartsWith($generatedRoot, [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Directory]::Exists($resolvedVerification)) {
            [IO.Directory]::Delete($resolvedVerification, $true)
        }
    }

    $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText(
        (Join-Path $resolvedOutput 'SHA256SUMS.txt'),
        "$hash  $packageName`r`n",
        [Text.UTF8Encoding]::new($false))
    Write-Output "Windows v$Version package created in $resolvedOutput"
} finally {
    Pop-Location
}
