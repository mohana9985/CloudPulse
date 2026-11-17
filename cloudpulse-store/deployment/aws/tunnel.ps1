# Open SSH tunnels from YOUR COMPUTER (Windows PowerShell) to the AWS instances.
# macOS / Linux: deployment/aws/tunnel.sh
#
# Local Docker keeps the normal ports (Grafana 3000, Prometheus 9090, gateway 8090, loadgen 8095,
# coordinator 8100). AWS is opened on DIFFERENT local ports taken from .env, so the local stack and
# the AWS tunnel never clash (AWS_*_LOCAL_PORT: 3001 / 9091 / 8091 / 8096 / 8101).
# IPs, key path, user and ports all come from cloudpulse-store\.env (never from flags).
#
# Usage (from cloudpulse-store\):  powershell -ExecutionPolicy Bypass -File deployment\aws\tunnel.ps1
# Ctrl+C closes the tunnels.
$ErrorActionPreference = "Stop"

$ProjectDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$EnvFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Error "$EnvFile not found (Copy-Item .env.example .env, then fill the AWS_* lines)"
}

$EnvValues = @{}
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $EnvValues[$Matches[1]] = $Matches[2].Trim('"')
    }
}
function Get-EnvValue($Name, $Default) {
    if ($EnvValues.ContainsKey($Name) -and $EnvValues[$Name] -ne "") { return $EnvValues[$Name] }
    return $Default
}
function Test-IsSet($Value) { return ($Value -and -not $Value.StartsWith("<")) }

$Key      = (Get-EnvValue "AWS_SSH_KEY" "~/.ssh/cloudpulse-key.pem") -replace '^~', $HOME
$UserName = Get-EnvValue "AWS_SSH_USER" "ubuntu"
$StoreIp  = Get-EnvValue "AWS_STORE_PUBLIC_IP" ""
$SchedIp  = Get-EnvValue "AWS_SCHEDULER_PUBLIC_IP" ""
$Grafana  = Get-EnvValue "AWS_GRAFANA_LOCAL_PORT" "3001"
$Prom     = Get-EnvValue "AWS_PROMETHEUS_LOCAL_PORT" "9091"
$Gateway  = Get-EnvValue "AWS_GATEWAY_LOCAL_PORT" "8091"
$Loadgen  = Get-EnvValue "AWS_LOADGEN_LOCAL_PORT" "8096"
$Coord    = Get-EnvValue "AWS_COORDINATOR_LOCAL_PORT" "8101"

if (-not (Test-IsSet $StoreIp)) { Write-Error "set AWS_STORE_PUBLIC_IP in $EnvFile" }
if (-not (Test-Path $Key)) { Write-Error "SSH key not found: $Key (AWS_SSH_KEY in .env)" }

$SshOpts = @("-i", $Key, "-N", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30")
$Procs = @()
$Procs += Start-Process ssh -NoNewWindow -PassThru -ArgumentList ($SshOpts + @(
    "-L", "${Grafana}:127.0.0.1:3000", "-L", "${Prom}:127.0.0.1:9090",
    "-L", "${Gateway}:127.0.0.1:8090", "-L", "${Loadgen}:127.0.0.1:8095",
    "$UserName@$StoreIp"))
Write-Host "==> Store EC2 ($StoreIp)"
Write-Host "    Grafana     http://localhost:$Grafana"
Write-Host "    Prometheus  http://localhost:$Prom"
Write-Host "    Gateway     http://localhost:$Gateway/gateway/health"
Write-Host "    Loadgen     http://localhost:$Loadgen/loadgen/health"

if (Test-IsSet $SchedIp) {
    $Procs += Start-Process ssh -NoNewWindow -PassThru -ArgumentList ($SshOpts + @(
        "-L", "${Coord}:127.0.0.1:8100", "$UserName@$SchedIp"))
    Write-Host "==> Dashboard EC2 ($SchedIp)"
    Write-Host "    Coordinator http://localhost:$Coord/health"
}
Write-Host "Tunnels open. Ctrl+C to close."
try { $Procs | Wait-Process }
finally { $Procs | Where-Object { -not $_.HasExited } | Stop-Process -Force }
