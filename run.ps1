param(
    [switch]$Full,
    [switch]$SetupOnly,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if ($Help) {
    Write-Host "Usage: .\run.ps1 [-Full] [-SetupOnly]"
    Write-Host "  -Full       Install the optional Florence-2 dependencies."
    Write-Host "  -SetupOnly  Install dependencies without starting Streamlit."
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/"
}

$syncArguments = @("sync", "--locked", "--python", "3.12", "--extra", "app", "--extra", "ocr")
if ($Full) {
    $syncArguments += @("--extra", "vlm")
}

Write-Host "[ClaimKit] Preparing the local environment..."
& uv @syncArguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($SetupOnly) {
    Write-Host "[ClaimKit] Setup complete."
    exit 0
}

Write-Host "[ClaimKit] Opening http://127.0.0.1:8501"
& uv run streamlit run src/claimkit/app.py
exit $LASTEXITCODE
