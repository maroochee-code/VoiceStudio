# 바탕화면에 VoiceStudio 바로가기 만들기
# 실행: powershell -ExecutionPolicy Bypass -File scripts\make_shortcut.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")   # OneDrive 바탕화면도 자동으로 찾음
$Icon = "$Root\assets\voicestudio.ico"

if (-not (Test-Path $Icon)) { & "$Root\.venv\Scripts\python.exe" "$Root\scripts\make_icon.py" }

$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut("$Desktop\VoiceStudio.lnk")
$Lnk.TargetPath = "$Root\VoiceStudio.bat"
$Lnk.WorkingDirectory = $Root
$Lnk.IconLocation = "$Icon,0"
$Lnk.Description = "VoiceStudio - 로컬 음성 AI 툴"
$Lnk.WindowStyle = 7   # 검은 창은 최소화된 상태로 시작
$Lnk.Save()
Write-Host "바탕화면에 바로가기를 만들었습니다: $Desktop\VoiceStudio.lnk" -ForegroundColor Green
