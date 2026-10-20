$ErrorActionPreference = 'Stop'
$root = Join-Path $env:APPDATA 'ai.anodhas.handy'
$model = Join-Path $root 'models\parakeet-tdt-0.6b-v3-Q4_K_M.gguf'
if ((Get-FileHash $model -Algorithm SHA256).Hash.ToLower() -ne 'b68557be1e3c40207fd7c4bd9d63f1d3316b963f15325bfb0cc16a8bb0ffd181') { throw 'Model integrity check failed' }
$path = Join-Path $root 'settings_store.json'
$state = if (Test-Path $path) { Get-Content $path -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $state.PSObject.Properties['settings']) { $state | Add-Member NoteProperty settings ([pscustomobject]@{}) }
$s = $state.settings
if (-not $s.PSObject.Properties['selected_model'] -or -not $s.selected_model) {
  $s | Add-Member -Force NoteProperty selected_model 'handy-computer/parakeet-tdt-0.6b-v3-gguf/parakeet-tdt-0.6b-v3-Q4_K_M.gguf'
  $s | Add-Member -Force NoteProperty onboarding_completed $true
}
$s | Add-Member -Force NoteProperty update_checks_enabled $false
$temp = "$path.tmp"
[System.IO.File]::WriteAllText($temp, ($state | ConvertTo-Json -Depth 100), (New-Object System.Text.UTF8Encoding($false)))
Move-Item $temp $path -Force
