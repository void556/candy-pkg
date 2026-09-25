# Candy Package Manager - Installer Script
$ErrorActionPreference = "Stop"

$CandyBaseDir = "C:\Candy"
$CandyAppsDir = "C:\Candy\apps"
$CandyExe     = "$CandyBaseDir\candy.exe"

# GitHub Repository Details
$GitHubUser = "void556"
$GitHubRepo = "candy-pkg"
$ReleaseTag = "v1.0"

# Tagged pre-release download URL
$ReleaseUrl = "https://github.com/$GitHubUser/$GitHubRepo/releases/download/$ReleaseTag/candy.exe"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Installing Candy Package Manager    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Create base directories
if (-not (Test-Path -Path $CandyBaseDir)) {
    Write-Host "[*] Creating base folder at $CandyBaseDir..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $CandyBaseDir -Force | Out-Null
}

if (-not (Test-Path -Path $CandyAppsDir)) {
    Write-Host "[*] Creating apps folder at $CandyAppsDir..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $CandyAppsDir -Force | Out-Null
}

# 2. Download executable
Write-Host "[*] Downloading candy.exe from GitHub Release ($ReleaseTag)..." -ForegroundColor Yellow
try {
    # Enable TLS 1.2 for GitHub downloads
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $ReleaseUrl -OutFile $CandyExe -UseBasicParsing
    Write-Host "[+] Binary downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "[!] Download failed from $ReleaseUrl" -ForegroundColor Red
    Write-Host "[!] Error details: $_" -ForegroundColor Red
    exit 1
}

# 3. Register paths in Windows User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathsToRegister = @($CandyBaseDir, $CandyAppsDir)
$Updated = $false

foreach ($Path in $PathsToRegister) {
    if ($UserPath -notlike "*$Path*") {
        Write-Host "[*] Adding $Path to User PATH..." -ForegroundColor Yellow
        $UserPath = "$UserPath;$Path"
        $Updated = $true
    } else {
        Write-Host "[+] $Path is already in PATH." -ForegroundColor Green
    }
}

if ($Updated) {
    # Save to User Registry
    [Environment]::SetEnvironmentVariable("Path", $UserPath, "User")
    
    # Apply to active session
    $env:Path = "$env:Path;$CandyBaseDir;$CandyAppsDir"
    
    Write-Host "[+] Registry PATH updated successfully!" -ForegroundColor Green
}

Write-Host "`n[🎉] Candy successfully installed!" -ForegroundColor Green
Write-Host "Open a new PowerShell window and run 'candy list' to get started." -ForegroundColor Cyan
