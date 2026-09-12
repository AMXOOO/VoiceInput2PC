param([switch]$EnableAutostart)
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$workspace = Split-Path -Parent (Split-Path -Parent $project)
$source = Join-Path $project 'dist\VoiceInput2PCReceiver.exe'
$destination = Join-Path $workspace 'outputs\语音输入电脑-电脑接收端.exe'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw '请先构建接收端' }
$destination = [IO.Path]::GetFullPath($destination)
if (Test-Path -LiteralPath $destination) {
    $backup = Join-Path $project ('build\VoiceInput2PCReceiver-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.exe')
    Copy-Item -LiteralPath $destination -Destination $backup
}
# Stop only this known executable and wait until its Windows file handle is released.
$owned = @(Get-Process | Where-Object { $_.Path -eq $destination })
foreach ($item in $owned) { Stop-Process -Id $item.Id }
foreach ($item in $owned) {
    if (-not $item.WaitForExit(10000)) { throw '接收端尚未退出，已停止更新' }
}
Copy-Item -LiteralPath $source -Destination $destination -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    throw '交付文件校验失败，没有启动'
}
if ($EnableAutostart) {
    New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name VoiceInput2PC `
        -Value ('"' + $destination + '"') -PropertyType String -Force | Out-Null
}
Start-Process -FilePath $destination -WindowStyle Hidden
Write-Output '接收端文件已校验并启动；旧版本保存在 build 中。请继续检查健康接口和真实输入。'
