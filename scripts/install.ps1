# VoiceStudio 설치 스크립트 (처음 설치 또는 다시 설치할 때)
# 실행: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# 모든 파일은 D:\Github\VoiceStudio 아래에만 설치된다.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:UV_CACHE_DIR = "$Root\.uv\cache"
$env:UV_PYTHON_INSTALL_DIR = "$Root\.uv\python"
$env:UV_HTTP_TIMEOUT = "300"
$Py = "$Root\.venv\Scripts\python.exe"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv가 설치되어 있지 않습니다. https://docs.astral.sh/uv/ 에서 설치하세요."
}

Step "1. 파이썬 3.10 + 가상환경"
uv python install 3.10
if (-not (Test-Path $Py)) { uv venv .venv --python 3.10 }

Step "2. 패키지 설치 (정확한 버전: requirements-lock.txt)"
# melotts는 아래 3단계에서 따로 설치하므로 lock 파일에서 뺀다
$lock = Get-Content requirements-lock.txt | Where-Object { $_ -notmatch "melotts" -and $_ -notmatch "^unidic==" }
$tmp = Join-Path $env:TEMP "voicestudio-lock.txt"
$lock | Set-Content -Encoding ascii $tmp
uv pip install --python $Py -r $tmp --index-url https://pypi.org/simple `
    --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match

Step "3. MeloTTS (engines\MeloTTS)"
if (-not (Test-Path engines\MeloTTS)) {
    git clone --depth 1 https://github.com/myshell-ai/MeloTTS.git engines\MeloTTS
}
uv pip install --python $Py -e engines\MeloTTS -c constraints.txt --index-url https://pypi.org/simple `
    --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
# 버그 기록 002: 대용량 일본어 사전 unidic 제거 (unidic-lite 사용)
uv pip uninstall --python $Py unidic
# 버그 기록 001: librosa 0.9.1용
uv pip install --python $Py "setuptools<81"

Step "4. 한국어 형태소 분석기 (engines\mecab_ko, 버그 기록 003)"
uv pip install --python $Py --target engines\mecab_ko --no-deps python-mecab-ko==1.3.7 python-mecab-ko-dic==2.1.1.post2

Step "4-1. nltk 사전 폴더 (C: 대신 D:에 받도록, 버그 기록 004)"
New-Item -ItemType Directory -Force "$Root\.venv\nltk_data", "$Root\models\nltk_data" | Out-Null

Step "5. .env 준비"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Step "6. 확인"
& $Py app\gpu_check.py
Write-Host "`n설치 완료. 테스트: .venv\Scripts\python.exe -m pytest tests -q" -ForegroundColor Green
