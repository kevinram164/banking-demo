# Build và push từng service lên GitLab Container Registry (PowerShell).
# Repo: registry.gitlab.com/kiettt164/banking-demo-payment
#
# Cách dùng:
#   1. docker login registry.gitlab.com
#   2. Từ thư mục gốc: .\scripts\push-gitlab.ps1
#   3. Hoặc với tag: .\scripts\push-gitlab.ps1 -Tag v1.0.0

param([string]$Tag = "latest")

$Registry = "registry.gitlab.com/kiettt164/banking-demo-payment"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\services")) { $Root = (Get-Location).Path }

Write-Host "Registry: $Registry"
Write-Host "Tag: $Tag"
Write-Host "---"

function Build-And-Push {
  param([string]$Name, [string]$Dockerfile, [string]$Context)
  Write-Host "Build $Name..."
  docker build -t "${Registry}/${Name}:${Tag}" -f $Dockerfile $Context
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "Push ${Registry}/${Name}:${Tag}"
  docker push "${Registry}/${Name}:${Tag}"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "Done $Name"
  Write-Host "---"
}

Set-Location $Root
Build-And-Push "auth-service" "services/auth-service/Dockerfile" "."
Build-And-Push "account-service" "services/account-service/Dockerfile" "."
Build-And-Push "transfer-service" "services/transfer-service/Dockerfile" "."
Build-And-Push "notification-service" "services/notification-service/Dockerfile" "."
Build-And-Push "frontend" "frontend/Dockerfile" "./frontend"

Write-Host "All images pushed to $Registry with tag $Tag"
