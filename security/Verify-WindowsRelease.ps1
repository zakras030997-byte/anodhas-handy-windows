[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$InstallerPath,
  [Parameter(Mandatory)][string]$PayloadRoot,
  [Parameter(Mandatory)][string]$PublisherThumbprint,
  [string]$ReportPath = 'windows-release-verification.json'
)
$ErrorActionPreference = 'Stop'
$installer = Get-Item -LiteralPath $InstallerPath
$payload = Get-Item -LiteralPath $PayloadRoot
if (-not $payload.PSIsContainer) { throw 'PayloadRoot must be the complete unpacked release directory.' }
$thumbprint = $PublisherThumbprint.Replace(' ','').ToUpperInvariant()
$files = @($installer) + @(Get-ChildItem $payload.FullName -File -Recurse | Where-Object Extension -in '.exe','.dll')
$records = foreach ($file in $files) {
  $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
  $publisherMatches = $signature.SignerCertificate -and $signature.SignerCertificate.Thumbprint -eq $thumbprint
  $microsoftDependency = $file.FullName -ne $installer.FullName -and $signature.SignerCertificate.Subject -match 'O=Microsoft Corporation'
  [pscustomobject]@{
    File = $file.FullName
    SHA256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    Signature = $signature.Status.ToString()
    Publisher = $signature.SignerCertificate.Subject
    Accepted = $signature.Status -eq 'Valid' -and ($publisherMatches -or $microsoftDependency)
  }
}
$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath
if ($records | Where-Object { -not $_.Accepted }) { throw 'Release blocked: missing, invalid, or unexpected Authenticode publisher signature. No files were modified.' }
$status = Get-MpComputerStatus
if (-not $status.AMServiceEnabled -or -not $status.AntivirusEnabled) { throw 'Release blocked: Microsoft Defender is not active.' }
Update-MpSignature
$platform = Get-ChildItem "$env:ProgramData/Microsoft/Windows Defender/Platform" -Directory | Sort-Object Name -Descending | Select-Object -First 1
$scanner = Join-Path $platform.FullName 'MpCmdRun.exe'
foreach ($target in @($installer.FullName, $payload.FullName)) {
  & $scanner -Scan -ScanType 3 -File $target -DisableRemediation
  if ($LASTEXITCODE -ne 0) { throw "Release blocked: Defender returned $LASTEXITCODE for $target" }
}
Write-Host 'Local signature and antivirus checks passed. Google/SmartScreen reputation and target-device acceptance remain separate checks.'
