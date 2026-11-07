param(
    [ValidateSet('smoke', 'full', 'ramp')]
    [string]$Profile = 'smoke',
    [string]$Rate = '',
    [string]$Duration = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$evidenceRoot = Join-Path $projectRoot 'evidence\impl2\nfr'
$databasePath = Join-Path $evidenceRoot "story-3.5-$Profile.db"
$stdoutPath = Join-Path $evidenceRoot "story-3.5-$Profile-stdout.txt"
$stderrPath = Join-Path $evidenceRoot "story-3.5-$Profile-stderr.txt"
$resultPath = Join-Path $evidenceRoot 'story-3.5-k6.txt'
$k6 = Get-ChildItem -Path (Join-Path $projectRoot '.tools') -Filter 'k6.exe' -Recurse | Select-Object -First 1
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not $k6) { throw 'Portable k6 executable was not found under .tools.' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment Python was not found.' }
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null

$resolvedEvidence = (Resolve-Path $evidenceRoot).Path
if (-not $databasePath.StartsWith($resolvedEvidence, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to clean a database outside the Impl-2 NFR evidence directory.'
}
Remove-Item -LiteralPath $databasePath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

$env:GPU_TWIN_DATABASE_URL = "sqlite+pysqlite:///$($databasePath.Replace('\', '/'))"
$env:GPU_TWIN_LIVENESS_SCAN_SECONDS = '0'
$env:GPU_TWIN_POLICY_VERSION = 'impl2-nfr-v1'
Push-Location $projectRoot
try {
    & uv run alembic upgrade head | Out-Null
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
        do {
            $children = Get-CimInstance Win32_Process | Where-Object {
                $_.ParentProcessId -in $serverPids -and $_.ProcessId -notin $serverPids
            } | Select-Object -ExpandProperty ProcessId
            $serverPids += @($children)
        } while ($children)

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
