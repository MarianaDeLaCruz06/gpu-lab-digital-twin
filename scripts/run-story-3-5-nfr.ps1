param(
    [ValidateSet('smoke', 'full', 'ramp')]
    [string]$Profile = 'smoke',
    [ValidateSet('sqlite', 'postgres')]
    [string]$Backend = 'sqlite',
    [string]$DatabaseUrl = '',
    [string]$Rate = '',
    [string]$Duration = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$evidenceRoot = Join-Path $projectRoot 'evidence\impl2\nfr'
$artifactStem = "story-3.5-$Profile"
if ($Backend -eq 'postgres') { $artifactStem = "story-3.5-postgres-$Profile" }
if ($Profile -eq 'ramp' -and $Rate) { $artifactStem = "$artifactStem-$Rate" }
$databasePath = Join-Path $evidenceRoot "$artifactStem.db"
$stdoutPath = Join-Path $evidenceRoot "$artifactStem-stdout.txt"
$stderrPath = Join-Path $evidenceRoot "$artifactStem-stderr.txt"
$resultPath = if ($Backend -eq 'postgres') {
    Join-Path $evidenceRoot "$artifactStem-k6.txt"
} else {
    Join-Path $evidenceRoot 'story-3.5-k6.txt'
}
$portableK6Root = Join-Path $projectRoot '.tools'
$k6 = if (Test-Path -LiteralPath $portableK6Root) {
    Get-ChildItem -Path $portableK6Root -Filter 'k6.exe' -Recurse | Select-Object -First 1
} else {
    Get-Command 'k6.exe' -ErrorAction SilentlyContinue
}
if (-not $k6 -and (Test-Path -LiteralPath 'C:\Program Files\k6\k6.exe')) {
    $k6 = Get-Item -LiteralPath 'C:\Program Files\k6\k6.exe'
}
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not $k6) { throw 'k6 executable was not found under .tools, PATH, or Program Files.' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment Python was not found.' }
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null

$resolvedEvidence = (Resolve-Path $evidenceRoot).Path
if ($Backend -eq 'sqlite') {
    if (-not $databasePath.StartsWith($resolvedEvidence, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean a database outside the Impl-2 NFR evidence directory.'
    }
    Remove-Item -LiteralPath $databasePath -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

if ($Backend -eq 'postgres') {
    if (-not $DatabaseUrl) {
        throw 'PostgreSQL runs require -DatabaseUrl so the target backend is explicit.'
    }
    $env:GPU_TWIN_DATABASE_URL = $DatabaseUrl
} else {
    $env:GPU_TWIN_DATABASE_URL = "sqlite+pysqlite:///$($databasePath.Replace('\', '/'))"
}
$env:GPU_TWIN_LIVENESS_SCAN_SECONDS = '0'
$env:GPU_TWIN_POLICY_VERSION = 'impl2-nfr-v1'
Push-Location $projectRoot
try {
    if ($Backend -eq 'postgres') {
        & uv run alembic downgrade base | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL reset migration failed.' }
    }
    & uv run alembic upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
    $baselinePythonPids = @(Get-Process -Name python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $server = Start-Process -FilePath $python -ArgumentList '-m', 'uvicorn', 'gpu_lab_twin.main:app', '--host', '127.0.0.1', '--port', '8766' -WindowStyle Hidden -PassThru
    try {
        $ready = $false
        $deadline = [DateTimeOffset]::UtcNow.AddSeconds(30)
        while (-not $ready -and [DateTimeOffset]::UtcNow -lt $deadline) {
            try {
                $reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/ready' -TimeoutSec 1
                $ready = $reply.status -eq 'ready'
            } catch {
                [System.Threading.ManualResetEventSlim]::new($false).Wait(100) | Out-Null
            }
        }
        if (-not $ready) { throw 'NFR service did not become ready.' }

        $env:BASE_URL = 'http://127.0.0.1:8766'
        $env:K6_PROFILE = $Profile
        if ($Rate) { $env:RAMP_RATE = $Rate }
        if ($Duration) { $env:RAMP_DURATION = $Duration }
        $serverPids = @($server.Id)
        try {
            do {
                $children = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                    $_.ParentProcessId -in $serverPids -and $_.ProcessId -notin $serverPids
                } | Select-Object -ExpandProperty ProcessId
                $serverPids += @($children)
            } while ($children)
        } catch {
            $newPythonPids = @(Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
                $_.Id -notin $baselinePythonPids
            } | Select-Object -ExpandProperty Id)
            $serverPids = @($serverPids + $newPythonPids | Sort-Object -Unique)
            Write-Warning "Process-tree discovery failed; RSS fallback tracks newly launched Python processes. $($_.Exception.Message)"
        }

        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $k6.FullName
        $startInfo.Arguments = 'run tests/nfr/telemetry-storm.js'
        $startInfo.WorkingDirectory = $projectRoot
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $load = [System.Diagnostics.Process]::new()
        $load.StartInfo = $startInfo
        $load.Start() | Out-Null
        $stdoutTask = $load.StandardOutput.ReadToEndAsync()
        $stderrTask = $load.StandardError.ReadToEndAsync()
        $maxRss = 0L
        while (-not $load.HasExited) {
            $rss = (Get-Process -Id $serverPids -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum
            $maxRss = [Math]::Max($maxRss, $rss)
            $load.WaitForExit(100) | Out-Null
        }
        $load.WaitForExit()
        $exitCode = $load.ExitCode
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        Set-Content -LiteralPath $stdoutPath -Value $stdout -Encoding utf8
        Set-Content -LiteralPath $stderrPath -Value $stderr -Encoding utf8
        $rss = (Get-Process -Id $serverPids -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum
        $maxRss = [Math]::Max($maxRss, $rss)
        $lines = @(
            "COMMAND: $($k6.FullName) run tests/nfr/telemetry-storm.js",
            "PROFILE: $Profile",
            "BACKEND: $Backend",
            "RATE: $Rate",
            "DURATION: $Duration",
            "SERVER_PID: $($server.Id)",
            "MAX_RSS_BYTES: $maxRss",
            "MAX_RSS_MIB: $([Math]::Round($maxRss / 1MB, 2))",
            "K6_EXIT_CODE: $exitCode",
            '',
            'STDOUT:',
            $stdout,
            '',
            'STDERR:',
            $stderr
        )
        Set-Content -LiteralPath $resultPath -Value $lines -Encoding utf8
        if ($exitCode -ne 0) { throw "k6 exited with code $exitCode." }
    } finally {
        if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    }
} finally {
    Pop-Location
}
