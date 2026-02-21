# Enable Windows Long Paths (required for TensorFlow install in deep paths)
# Run this script as Administrator: Right-click PowerShell -> Run as administrator, then:
#   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force; .\enable-long-paths.ps1

$path = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
$name = "LongPathsEnabled"
$value = 1

if (-not (Test-Path $path)) {
    New-Item -Path $path -Force
}
New-ItemProperty -Path $path -Name $name -Value $value -PropertyType DWORD -Force
Write-Host "Long paths enabled. Reboot your PC (or at least close and reopen your terminal) then run: pip install tensorflow"
