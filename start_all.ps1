param(
    [switch]$Stop
)

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidsFile = Join-Path $BaseDir ".pids.ps1"
$VenvPython = Join-Path $BaseDir "venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Python executable not found in venv. Expected: $VenvPython"
}

function Stop-AllServices {
    if (Test-Path $PidsFile) {
        Get-Content $PidsFile | ForEach-Object {
            $pid = $_.Trim()
            if ($pid) {
                Stop-Process -Id ([int]$pid) -ErrorAction SilentlyContinue
                Write-Host "Stopped PID $pid"
            }
        }
        Remove-Item $PidsFile -Force
        Write-Host "All services stopped."
    } else {
        Write-Host "No running services found."
    }
}

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$RelativeDir,
        [int]$Port
    )

    $ServiceDir = Join-Path $BaseDir $RelativeDir
    Write-Host "Starting $Name on port $Port ..."

    & $VenvPython -m pip install -r (Join-Path $ServiceDir "requirements.txt") -q

    $process = Start-Process -FilePath $VenvPython `
        -ArgumentList @("-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$Port", "--reload") `
        -WorkingDirectory $ServiceDir `
        -PassThru

    Add-Content -Path $PidsFile -Value $process.Id
    Write-Host "$Name started (PID $($process.Id))"
}

if ($Stop) {
    Stop-AllServices
    exit 0
}

if (Test-Path $PidsFile) {
    Remove-Item $PidsFile -Force
}

Write-Host ""
Write-Host "Hotel Booking System - Starting All Services"
Write-Host "=================================================="

Start-ServiceProcess -Name "Guest Service" -RelativeDir "services\guest_service" -Port 8001
Start-ServiceProcess -Name "Room Service" -RelativeDir "services\room_service" -Port 8002
Start-ServiceProcess -Name "Booking Service" -RelativeDir "services\booking_service" -Port 8003
Start-ServiceProcess -Name "Payment Service" -RelativeDir "services\payment_service" -Port 8004
Start-ServiceProcess -Name "Notification Service" -RelativeDir "services\notification_service" -Port 8005

Write-Host ""
Write-Host "Waiting 3 seconds for services to initialize..."
Start-Sleep -Seconds 3

Start-ServiceProcess -Name "API Gateway" -RelativeDir "api_gateway" -Port 8000

Write-Host ""
Write-Host "=================================================="
Write-Host "All services are running!"
Write-Host ""
Write-Host "API Gateway docs:        http://localhost:8000/docs"
Write-Host "Guest Service docs:      http://localhost:8001/docs"
Write-Host "Room Service docs:       http://localhost:8002/docs"
Write-Host "Booking Service docs:    http://localhost:8003/docs"
Write-Host "Payment Service docs:    http://localhost:8004/docs"
Write-Host "Notification Service docs: http://localhost:8005/docs"
Write-Host ""
Write-Host "Run .\start_all.ps1 -Stop to stop all services."
Write-Host "=================================================="
