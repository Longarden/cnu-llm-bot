# 4 워커 + planner_loop 백그라운드 시작 (Windows hidden process).
# 노트북 절전 OFF 상태에서 lid close해도 계속 돈다.
#
# 사용: powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
# 중단: New-Item -ItemType File data\planner\stop

$root = 'C:\Users\dmsak\cnu-llm-bot'
$py   = 'C:\Users\dmsak\miniconda3\python.exe'
$logdir = "$root\data\planner"

New-Item -ItemType Directory -Force -Path $logdir | Out-Null
$stop = "$logdir\stop"
if (Test-Path $stop) {
    Remove-Item $stop -Force
    Write-Host "이전 stop 파일 제거"
}

# 4 워커의 done 파일 청소 (재시작이면 새로 만들게)
Get-ChildItem "$root\data\crawled_staging" -Filter '*_v2.done' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem "$logdir" -Filter '*.log' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem "$logdir" -Filter '*.err.log' -ErrorAction SilentlyContinue | Remove-Item -Force
if (Test-Path "$logdir\sweep_done.txt") { Remove-Item "$logdir\sweep_done.txt" -Force }

function Launch($name, $script, $extra=@()) {
    $stdout = "$logdir\$name.log"
    $stderr = "$logdir\$name.err.log"
    $argList = @($script) + $extra
    Write-Host "Launching $name -> $stdout"
    $p = Start-Process -FilePath $py `
        -ArgumentList $argList `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError  $stderr `
        -PassThru
    "$name`tPID=$($p.Id)" | Out-File "$logdir\pids.txt" -Append -Encoding utf8
    return $p
}

"" | Out-File "$logdir\pids.txt" -Encoding utf8

Launch 'worker_dept'        "$root\scripts\crawl_workers\worker_dept_v2.py"
Launch 'worker_regulations' "$root\scripts\crawl_workers\worker_regulations_v2.py"
Launch 'worker_admission'   "$root\scripts\crawl_workers\worker_admission_v2.py"
Launch 'worker_life'        "$root\scripts\crawl_workers\worker_life_v2.py"
Launch 'planner'            "$root\scripts\planner_loop.py"

Write-Host ''
Write-Host '=== 모든 워커 + planner 띄움 (hidden background) ==='
Write-Host "로그 디렉토리: $logdir"
Write-Host "진행 보기:     Get-Content $logdir\progress.log -Wait"
Write-Host "워커별 로그:   Get-Content $logdir\worker_dept.log -Wait"
Write-Host "PID 목록:      $logdir\pids.txt"
Write-Host "중단:          New-Item -ItemType File $stop"
Write-Host "이제 노트북 덮개 닫아도 계속 돈다 (sleep OFF 적용된 상태)"
