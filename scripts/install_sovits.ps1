# GPT-SoVITS 설치 스크립트 (목소리 학습용, 별도 가상환경)
# 실행: powershell -ExecutionPolicy Bypass -File scripts\install_sovits.ps1
# 설치 위치: D:\Github\VoiceStudio\engines\GPT-SoVITS  (다운로드 약 3GB, 설치 후 약 8GB)
# 필요: ffmpeg (winget install Gyan.FFmpeg)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Sv = "$Root\engines\GPT-SoVITS"
$Py = "$Sv\.venv\Scripts\python.exe"
$env:UV_CACHE_DIR = "$Root\.uv\cache"
$env:UV_PYTHON_INSTALL_DIR = "$Root\.uv\python"
$env:UV_HTTP_TIMEOUT = "300"
$env:HF_HOME = "$Root\models\huggingface"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "ffmpeg가 없습니다. PowerShell에서 'winget install Gyan.FFmpeg' 실행 후 다시 시도하세요."
}

Step "1. GPT-SoVITS 소스 받기"
if (-not (Test-Path $Sv)) {
    git clone --depth 1 https://github.com/RVC-Boss/GPT-SoVITS.git $Sv
}

Step "2. 전용 가상환경 (Python 3.10)"
if (-not (Test-Path $Py)) { uv venv "$Sv\.venv" --python 3.10 }

Step "3. 패키지 설치 (윈도우용으로 고친 목록: engines_setup\sovits-requirements.txt)"
uv pip install --python $Py -r "$Root\engines_setup\sovits-requirements.txt" `
    --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu124 `
    --index-strategy unsafe-best-match

Step "4. 대체 모듈(eunjeon, jieba_fast)과 경로 파일(users.pth)"
$site = "$Sv\.venv\Lib\site-packages"
Copy-Item -Recurse -Force "$Root\engines_setup\sovits_shims\*" $site
$d = $Sv -replace '\\', '/'
$pth = @($d, "$d/GPT_SoVITS/BigVGAN", "$d/tools", "$d/tools/asr", "$d/GPT_SoVITS", "$d/tools/uvr5") -join "`n"
[IO.File]::WriteAllText("$site\users.pth", $pth + "`n")
# 버그 기록 004: nltk 사전이 C:로 가지 않도록 환경 안에 폴더를 만들어 둠
New-Item -ItemType Directory -Force "$Sv\.venv\nltk_data" | Out-Null
if (Test-Path "$Root\models\nltk_data") { Copy-Item -Recurse -Force "$Root\models\nltk_data\*" "$Sv\.venv\nltk_data\" }

Step "5. 사전 학습 모델 (v2Pro + v2, 약 1.6GB)"
& $Py -c "from huggingface_hub import snapshot_download; snapshot_download('lj1995/GPT-SoVITS', local_dir='$d/GPT_SoVITS/pretrained_models', allow_patterns=['chinese-hubert-base/*','chinese-roberta-wwm-ext-large/*','gsv-v2final-pretrained/*','v2Pro/s2Gv2Pro.pth','v2Pro/s2Dv2Pro.pth','s1v3.ckpt','sv/*'])"

Step "6. 확인"
& $Py -c "import torch; from eunjeon import Mecab; print('GPU:', torch.cuda.is_available(), '/ 한국어 분석:', Mecab().pos('확인')[0])"
Write-Host "`nGPT-SoVITS 설치 완료" -ForegroundColor Green
