param([switch]$ValidateOnly, [switch]$SkipDeviceTests)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$requiredSigning = @(
    'VOICEINPUT2PC_KEYSTORE',
    'VOICEINPUT2PC_STORE_PASSWORD',
    'VOICEINPUT2PC_KEY_ALIAS',
    'VOICEINPUT2PC_KEY_PASSWORD'
)
$missingSigning = @($requiredSigning | Where-Object {
    [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_))
})
if ($missingSigning.Count -gt 0) {
    throw ('Missing release signing environment: ' + ($missingSigning -join ', '))
}
if ($ValidateOnly) {
    Write-Output 'Release environment is complete.'
    exit 0
}

function Invoke-Checked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "A required build step failed with exit code $LASTEXITCODE."
    }
}

function Resolve-Python {
    if ($env:VOICEINPUT2PC_PYTHON) {
        return (Resolve-Path $env:VOICEINPUT2PC_PYTHON).Path
    }
    $local = Join-Path $project '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $local) { return (Resolve-Path $local).Path }
    $commonGit = (& git -C $project rev-parse --path-format=absolute --git-common-dir).Trim()
    $mainCheckout = Split-Path $commonGit -Parent
    $shared = Join-Path $mainCheckout '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $shared) { return (Resolve-Path $shared).Path }
    throw 'Python virtual environment was not found. Set VOICEINPUT2PC_PYTHON.'
}

function Resolve-Gradle {
    if ($env:VOICEINPUT2PC_GRADLE) {
        return (Resolve-Path $env:VOICEINPUT2PC_GRADLE).Path
    }
    $command = Get-Command gradle.bat -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'Gradle was not found. Set VOICEINPUT2PC_GRADLE.'
}

function Resolve-AndroidTool([string]$name) {
    if ([string]::IsNullOrWhiteSpace($env:ANDROID_HOME)) {
        throw 'ANDROID_HOME is required.'
    }
    $tools = @(Get-ChildItem -LiteralPath (Join-Path $env:ANDROID_HOME 'build-tools') -Directory |
        Sort-Object Name -Descending |
        ForEach-Object {
            Join-Path $_.FullName ($name + '.exe')
            Join-Path $_.FullName ($name + '.bat')
        } |
        Where-Object { Test-Path -LiteralPath $_ })
    if ($tools.Count -eq 0) { throw "$name was not found in ANDROID_HOME." }
    return $tools[0]
}

function Clear-GeneratedReadOnly([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $resolved = (Resolve-Path -LiteralPath $path).Path
    if (-not $resolved.StartsWith($project + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unexpected generated directory path.'
    }
    Get-ChildItem -LiteralPath $resolved -Recurse -Force | ForEach-Object {
        $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
    }
    $item = Get-Item -LiteralPath $resolved
    $item.Attributes = $item.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
}

Push-Location $project
try {
    $dirty = (& git status --porcelain --untracked-files=normal)
    if ($LASTEXITCODE -ne 0 -or $dirty) {
        throw 'Release builds require a clean Git worktree.'
    }

    $python = Resolve-Python
    Invoke-Checked $python @('scripts\fetch_tailcat.py')
    $go = (Get-Command go.exe -ErrorAction SilentlyContinue)
    if (-not $go) { $go = (Get-Command go -ErrorAction SilentlyContinue) }
    if (-not $go) { throw 'Go 1.27+ is required to build the Android Tailcat bridge.' }
    $gomobile = (Get-Command gomobile.exe -ErrorAction SilentlyContinue)
    if (-not $gomobile) { $gomobile = (Get-Command gomobile -ErrorAction SilentlyContinue) }
    if (-not $gomobile) { throw 'gomobile is required to build the Android Tailcat bridge.' }
    New-Item -ItemType Directory -Force -Path 'android\app\libs' | Out-Null
    Push-Location 'mobile\tailcatbridge'
    try {
        Invoke-Checked $gomobile.Source @('bind','-target=android/arm64','-androidapi=26',
            '-javapkg=io.github.amxooo.voiceinput2pc',
            '-o','..\..\android\app\libs\tailcatbridge.aar','.')
    } finally { Pop-Location }
    $gradle = Resolve-Gradle
    if ([string]::IsNullOrWhiteSpace($env:JAVA_HOME)) { throw 'JAVA_HOME is required.' }
    $javac = Join-Path $env:JAVA_HOME 'bin\javac.exe'
    $java = Join-Path $env:JAVA_HOME 'bin\java.exe'
    if (-not (Test-Path -LiteralPath $javac) -or -not (Test-Path -LiteralPath $java)) {
        throw 'JDK tools were not found under JAVA_HOME.'
    }
    $aapt = Resolve-AndroidTool 'aapt'
    $apksigner = Resolve-AndroidTool 'apksigner'

    Invoke-Checked $python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    New-Item -ItemType Directory -Force -Path 'tests\java-build' | Out-Null
    Invoke-Checked $javac @('-encoding', 'UTF-8', '-d', 'tests\java-build',
        'android\app\src\main\java\io\github\amxooo\voiceinput2pc\PairingConfig.java',
        'android\app\src\main\java\io\github\amxooo\voiceinput2pc\PairingCodec.java',
        'android\app\src\main\java\io\github\amxooo\voiceinput2pc\CommitTracker.java',
        'android\app\src\main\java\io\github\amxooo\voiceinput2pc\DraftLogic.java',
        'tests\PairingCodecTest.java', 'tests\CommitTrackerTest.java', 'tests\DraftLogicTest.java')
    Invoke-Checked $java @('-cp', 'tests\java-build', 'io.github.amxooo.voiceinput2pc.PairingCodecTest')
    Invoke-Checked $java @('-cp', 'tests\java-build', 'io.github.amxooo.voiceinput2pc.CommitTrackerTest')
    Invoke-Checked $java @('-cp', 'tests\java-build', 'io.github.amxooo.voiceinput2pc.DraftLogicTest')
    Clear-GeneratedReadOnly (Join-Path $project 'build')
    Clear-GeneratedReadOnly (Join-Path $project 'dist')
    Clear-GeneratedReadOnly (Join-Path $project 'android\app\build')
    Invoke-Checked $python @('-m', 'PyInstaller', '--noconfirm', '--clean', 'VoiceInput2PCReceiver.spec')
    $androidTasks = @('-p', 'android')
    if ($SkipDeviceTests) { $androidTasks += 'compileDebugAndroidTestJavaWithJavac' }
    else { $androidTasks += 'connectedDebugAndroidTest' }
    $androidTasks += @('assembleRelease', '--no-daemon')
    Invoke-Checked $gradle $androidTasks

    $bundle = Join-Path $project 'dist\VoiceInput2PCReceiver'
    $exe = Join-Path $bundle 'VoiceInput2PCReceiver.exe'
    $apk = Join-Path $project 'android\app\build\outputs\apk\release\app-release.apk'
    if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $apk)) {
        throw 'Expected build outputs were not produced.'
    }
    $versionInfo = (Get-Item -LiteralPath $exe).VersionInfo
    if ($versionInfo.FileVersion -ne '0.5.0.0' -or $versionInfo.ProductVersion -ne '0.5.0') {
        throw "Unexpected executable version metadata: $($versionInfo.FileVersion) / $($versionInfo.ProductVersion)"
    }
    Invoke-Checked $python @('scripts\verify_first_run_ui.py', $exe)
    Invoke-Checked $python @('scripts\verify_receiver_runtime.py', $exe)
    Invoke-Checked $apksigner @('verify', '--verbose', $apk)
    $permissions = @(& $aapt dump permissions $apk)
    if (($LASTEXITCODE -ne 0) -or
            ($permissions.Count -ne 2) -or
            ($permissions[1] -notmatch "android.permission.INTERNET")) {
        throw 'The Android APK permission set is not exactly INTERNET.'
    }
    $apkEntries = @(& $aapt list $apk)
    if ($LASTEXITCODE -ne 0 -or ($apkEntries -match '(^|/)pairing\.json$')) {
        throw 'The Android APK contains a private pairing asset.'
    }
    if (-not ($apkEntries -contains 'lib/arm64-v8a/libgojni.so')) {
        throw 'The Android APK is missing the Tailcat Go bridge runtime.'
    }
    if ($apkEntries -contains 'lib/arm64-v8a/libtailcat.so') {
        throw 'The Android APK still contains the superseded Tailcat CLI runtime.'
    }

    $output = Join-Path $project 'release\output'
    $releaseRoot = (Resolve-Path (Join-Path $project 'release')).Path
    $resolvedOutput = [IO.Path]::GetFullPath($output)
    if (-not $resolvedOutput.StartsWith($releaseRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unexpected release output path.'
    }
    Clear-GeneratedReadOnly $resolvedOutput
    if ([IO.Directory]::Exists($resolvedOutput)) { [IO.Directory]::Delete($resolvedOutput, $true) }
    [IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

    $apkName = 'VoiceInput2PC-Android-v0.5.0.apk'
    $zipName = 'VoiceInput2PC-Windows-v0.5.0.zip'
    $sumName = 'SHA256SUMS.txt'
    $publicApk = Join-Path $resolvedOutput $apkName
    $publicZip = Join-Path $resolvedOutput $zipName
    Copy-Item -LiteralPath $apk -Destination $publicApk

    $temporary = Join-Path ([IO.Path]::GetTempPath()) ('VoiceInput2PC-release-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($temporary) | Out-Null
    try {
        foreach ($item in (Get-ChildItem -LiteralPath $bundle -Force)) {
            Copy-Item -LiteralPath $item.FullName -Destination $temporary -Recurse
        }
        $quickStarts = @(Get-ChildItem -LiteralPath (Join-Path $project 'release') -File -Filter '*.txt')
        if ($quickStarts.Count -ne 1) { throw 'Expected exactly one tracked quick-start text file.' }
        Copy-Item -LiteralPath $quickStarts[0].FullName -Destination $temporary
        $zipInputs = @(Get-ChildItem -LiteralPath $temporary -Force | ForEach-Object FullName)
        Compress-Archive -LiteralPath $zipInputs -DestinationPath $publicZip -CompressionLevel Optimal
    } finally {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        $resolvedTemporary = [IO.Path]::GetFullPath($temporary)
        if ($resolvedTemporary.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Directory]::Exists($resolvedTemporary)) {
            Get-ChildItem -LiteralPath $resolvedTemporary -Recurse -Force | ForEach-Object {
                $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
            }
            $temporaryItem = Get-Item -LiteralPath $resolvedTemporary
            $temporaryItem.Attributes = $temporaryItem.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
            [IO.Directory]::Delete($resolvedTemporary, $true)
        }
    }

    Invoke-Checked $python @('scripts\verify_release_artifacts.py',
        '--apk', $publicApk, '--windows', $publicZip)

    $verification = Join-Path $project ('build\public-package-check-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($verification) | Out-Null
    try {
        Expand-Archive -LiteralPath $publicZip -DestinationPath $verification
        $packagedExe = Join-Path $verification 'VoiceInput2PCReceiver.exe'
        foreach ($required in @(
                $packagedExe,
                (Join-Path $verification '_internal\_tcl_data\init.tcl'),
                (Join-Path $verification '使用说明.txt'),
                (Join-Path $verification '_internal\tailcat\tailcat.exe'))) {
            if (-not (Test-Path -LiteralPath $required)) {
                throw "Packaged Windows archive is missing: $required"
            }
        }
        Invoke-Checked $python @('scripts\verify_first_run_ui.py', $packagedExe)
        Invoke-Checked $python @('scripts\verify_receiver_runtime.py', $packagedExe)
    } finally {
        $resolvedVerification = [IO.Path]::GetFullPath($verification)
        $generatedRoot = [IO.Path]::GetFullPath((Join-Path $project 'build')) + [IO.Path]::DirectorySeparatorChar
        if ($resolvedVerification.StartsWith($generatedRoot, [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Directory]::Exists($resolvedVerification)) {
            Get-ChildItem -LiteralPath $resolvedVerification -Recurse -Force | ForEach-Object {
                $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
            }
            [IO.Directory]::Delete($resolvedVerification, $true)
        }
    }

    $apkHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $publicApk).Hash.ToLowerInvariant()
    $zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $publicZip).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText((Join-Path $resolvedOutput $sumName),
        "$apkHash  $apkName`r`n$zipHash  $zipName`r`n", [Text.UTF8Encoding]::new($false))
    $actualNames = @(Get-ChildItem -LiteralPath $resolvedOutput -File | Sort-Object Name |
        ForEach-Object Name)
    $expectedNames = @($sumName, $apkName, $zipName) | Sort-Object
    if (($actualNames -join "`n") -ne ($expectedNames -join "`n")) {
        throw 'Release output contains unexpected files.'
    }
    Write-Output "Public release artifacts created in $resolvedOutput"
} finally {
    Pop-Location
}
