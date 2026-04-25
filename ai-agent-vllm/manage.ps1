<#
.SYNOPSIS
  vLLM Model Manager — start, stop, and monitor individual models.

.DESCRIPTION
  Each model in docker-compose.yml has a profile name. Use this script to
  manage them individually or all at once.

.EXAMPLE
  .\manage.ps1 status              # Show running containers
  .\manage.ps1 list                # List available profiles
  .\manage.ps1 start all           # Start every model
  .\manage.ps1 start qwen          # Start only the Qwen chat model
  .\manage.ps1 start embed         # Start only the embedding model
  .\manage.ps1 stop qwen           # Stop a specific model
  .\manage.ps1 restart qwen        # Restart a specific model
  .\manage.ps1 logs qwen           # Stream logs for a model
  .\manage.ps1 test                # Health-check all running vLLM containers
#>

param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("start", "stop", "restart", "logs", "status", "list", "test")]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Profile = "all"
)

# ── Registered models ─────────────────────────────────────────────────────────
# Keep this list in sync with docker-compose.yml profiles and .env ports.
# When you add a new model, append an entry here.
$models = @(
    [PSCustomObject]@{ Profile = "qwen";    Name = "Qwen2.5-7B-Instruct";    Task = "chat";      Port = 8000; Use = "SOP / letter / report generation" },
    [PSCustomObject]@{ Profile = "embed";   Name = "nomic-embed-text-v1";    Task = "embedding"; Port = 8001; Use = "Semantic search, profile similarity" },
    [PSCustomObject]@{ Profile = "vision";  Name = "Qwen2.5-VL-7B-Instruct"; Task = "vision";    Port = 8002; Use = "Passport / ID card OCR, image extraction" }
    # ── ADD NEW MODELS HERE ────────────────────────────────────────────────
    # [PSCustomObject]@{ Profile = "mistral"; Name = "Mistral-7B-Instruct"; Task = "chat"; Port = 8003; Use = "..." },
)

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Header([string]$text) {
    Write-Host ""
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "  $('─' * $text.Length)" -ForegroundColor DarkGray
}

function Invoke-Compose([string]$profileArg, [string]$action, [string[]]$extra = @()) {
    $cmd = @("docker", "compose", "--profile", $profileArg) + $action.Split(" ") + $extra
    Write-Host "  ▶ $($cmd -join ' ')" -ForegroundColor DarkGray
    & $cmd[0] $cmd[1..($cmd.Length - 1)]
}

# ── Commands ──────────────────────────────────────────────────────────────────
switch ($Command) {

    "list" {
        Write-Header "Available vLLM model profiles"
        $models | Format-Table -AutoSize -Property `
            @{L = "Profile"; E = { $_.Profile }},
            @{L = "Model";   E = { $_.Name }},
            @{L = "Task";    E = { $_.Task }},
            @{L = "Port";    E = { $_.Port }},
            @{L = "Use Case"; E = { $_.Use }}
        Write-Host "  Use 'all' to start/stop every model at once.`n" -ForegroundColor Yellow
    }

    "status" {
        Write-Header "Running vLLM containers"
        docker ps --filter "name=ai_agent_vllm" `
            --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        Write-Host ""
    }

    "start" {
        Write-Header "Starting profile: $Profile"
        Invoke-Compose $Profile "up -d"
    }

    "stop" {
        Write-Header "Stopping profile: $Profile"
        Invoke-Compose $Profile "down"
    }

    "restart" {
        Write-Header "Restarting profile: $Profile"
        Invoke-Compose $Profile "restart"
    }

    "logs" {
        Write-Header "Logs for profile: $Profile"
        Invoke-Compose $Profile "logs" @("-f", "--tail=100")
    }

    "test" {
        Write-Header "Health-checking all vLLM containers"
        foreach ($m in $models) {
            $url = "http://localhost:$($m.Port)/v1/models"
            try {
                $resp = Invoke-RestMethod -Uri $url -TimeoutSec 5 -ErrorAction Stop
                $modelIds = ($resp.data | ForEach-Object { $_.id }) -join ", "
                Write-Host "  ✅ :$($m.Port) ($($m.Profile)) → $modelIds" -ForegroundColor Green
            } catch {
                Write-Host "  ❌ :$($m.Port) ($($m.Profile)) → not reachable" -ForegroundColor Red
            }
        }
        Write-Host ""
    }
}
