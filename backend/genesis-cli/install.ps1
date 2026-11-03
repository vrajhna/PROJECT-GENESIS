# Genesis CLI installer — Windows (PowerShell, run as your user).
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [-Server http://127.0.0.1:8000]
param([string]$Server = "http://127.0.0.1:8000")
$Dest = Join-Path $HOME ".genesis"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Write-Host "downloading genesis cli from $Server ..."
Invoke-WebRequest -Uri "$Server/api/download/cli" -OutFile (Join-Path $Dest "cli.zip")
Expand-Archive -Path (Join-Path $Dest "cli.zip") -DestinationPath $Dest -Force
$Path = [Environment]::GetEnvironmentVariable("Path", "User")
if ($Path -notlike "*$Dest*") {
  [Environment]::SetEnvironmentVariable("Path", "$Path;$Dest", "User")
  Write-Host "added $Dest to your user PATH (reopen the terminal to use it)"
}
Write-Host "installed to $Dest\genesis"
Write-Host "try:  `$env:GENESIS_URL='$Server'; py $Dest\genesis status"
