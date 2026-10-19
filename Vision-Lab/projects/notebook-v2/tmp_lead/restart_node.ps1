# -*- coding: utf-8 -*-
<#
  إعادة تشغيل عقدة النوتبوك v2 بشكل آمن — راية اللّيد.

  ⚠️ ده بيوقف خدمة حيّة (واجهة 8110 + بوت @Afkary22Bot) لثواني.
  عشان كده السكربت **dry-run افتراضيًا**: بيقولك هيعمل إيه وبس.
  التشغيل الحقيقي لازم `-Go` صريحة.

  الخطوات (وكل خطوة بتتأكد قبل اللي بعدها):
    1) نلاقي اللي سامع على البورت + نتحقق إنه فعلًا start_node.py بتاعنا
    2) قياس «قبل»
    3) إيقاف الشجرة (الابن الحقيقي + أبوه الـvenv stub)
    4) نستنى البورت يفضى
    5) نحرّر الإيجار **صراحةً** عشان العقدة الجديدة تاخد القيادة فورًا
       (بدونها البوت ممكن يتأخر لحد 45 ثانية = TTL)
    6) نشغّل من جديد بنفس الـvenv
    7) نستنى البورت يفتح، ونتأكد إن البوت رجع قائد (من اللوج)
    8) قياس «بعد» + مقارنة

  الاستخدام:
    .venv\\Scripts\\python.exe ... ;  pwsh -File tmp_lead\\restart_node.ps1          # معاينة
    pwsh -File tmp_lead\\restart_node.ps1 -Go                                      # تنفيذ
#>
param(
  [int]$Port = 8110,
  [switch]$Go
)

$ErrorActionPreference = 'Stop'
$proj = 'G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2'
$py   = Join-Path $proj '.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

$report = [ordered]@{
  mode          = if ($Go) { 'GO' } else { 'DRY-RUN' }
  port          = $Port
  started_at    = (Get-Date).ToString('HH:mm:ss')
  steps         = @()
  aborted       = $null
}

function Note($name, $ok, $detail) {
  $script:report.steps += [ordered]@{ step = $name; ok = $ok; detail = $detail }
}

function Probe($path) {
  $code = @"
import json, time, urllib.request, urllib.error
url = "http://127.0.0.1:$Port$path"
s = time.time()
try:
    with urllib.request.urlopen(url, timeout=120) as r:
        b = r.read()
        print(json.dumps({"status": r.status, "secs": round(time.time()-s,3), "bytes": len(b)}))
except urllib.error.HTTPError as e:
    print(json.dumps({"status": e.code, "secs": round(time.time()-s,3), "bytes": 0}))
except Exception as e:
    print(json.dumps({"status": type(e).__name__, "secs": round(time.time()-s,3)}))
"@
  $out = $code | & $py - 2>$null | Select-Object -Last 1
  try { return ($out | ConvertFrom-Json) } catch { return [pscustomobject]@{ status = "parse-error"; secs = $null } }
}

# ---------------------------------------------------------------- 1) مين سامع؟
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
if (-not $conn) {
  Note 'locate' $false "مفيش حاجة سامعة على $Port — مفيش حاجة نوقفها"
  $report.aborted = 'no-listener'
  $report | ConvertTo-Json -Depth 6
  return
}
$realPid = [int]$conn.OwningProcess
$real = Get-CimInstance Win32_Process -Filter "ProcessId=$realPid"
$parentPid = [int]$real.ParentProcessId
$parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid" -ErrorAction SilentlyContinue

# تحقق صارم: ممنوع نقتل عملية مش بتاعتنا
$isOurs = ($real.CommandLine -like '*start_node.py*') -and ($real.CommandLine -like '*notebook-v2*')
if (-not $isOurs) {
  Note 'verify' $false "العملية $realPid مش start_node.py بتاعنا — **رفضنا نلمسها**"
  $report.aborted = 'not-ours'
  $report.real = @{ pid = $realPid; cmd = $real.CommandLine }
  $report | ConvertTo-Json -Depth 6
  return
}
$killList = @($realPid)
$parentIsStub = $parent -and ($parent.CommandLine -like '*notebook-v2*') -and
                ($parent.CommandLine -like '*start_node.py*')
if ($parentIsStub) { $killList += $parentPid }

Note 'locate' $true ("هنوقف: " + (($killList | ForEach-Object { "PID $_" }) -join ' + ') +
     "  (الابن الحقيقي $realPid / أبوه الـvenv stub $parentPid)")

# ---------------------------------------------------------------- 2) قياس «قبل»
$before = [ordered]@{}
foreach ($pth in '/', '/health', '/api/dashboard') { $before[$pth] = (Probe $pth) }
$report.before = $before
Note 'measure-before' $true ("/ = $($before['/'].secs)s · /health = $($before['/health'].secs)s · " +
     "/api/dashboard = $($before['/api/dashboard'].status)")

if (-not $Go) {
  Note 'dry-run' $true 'معاينة بس — مفيش حاجة اتغيرت. شغّل بـ-Go للتنفيذ.'
  $report.finished_at = (Get-Date).ToString('HH:mm:ss')
  $report | ConvertTo-Json -Depth 6
  return
}

# ---------------------------------------------------------------- 3) الإيقاف
foreach ($procId in ($killList | Sort-Object -Descending)) {
  try {
    Stop-Process -Id $procId -Force -ErrorAction Stop
    Note "kill-$procId" $true 'اتقفلت'
  } catch {
    Note "kill-$procId" $false $_.Exception.Message
  }
}

# ---------------------------------------------------------------- 4) البورت يفضى
$freed = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $still) { $freed = $true; break }
}
Note 'port-free' $freed ("اتفضى بعد $([math]::Round($i*0.5,1))s" )
if (-not $freed) {
  $report.aborted = 'port-still-busy'
  $report | ConvertTo-Json -Depth 6
  return
}

# ------------------------------------------------- 5) تحرير الإيجار صراحةً
$leaseCode = @'
import json, sys
sys.path.insert(0, r"PROJ")
from nb import ha
try:
    ha.release()
    st = ha.status()
    print(json.dumps({"released": True, "holder": st.get("effective_leader"),
                      "lease_valid": st.get("lease_valid")}, ensure_ascii=True, default=str))
except Exception as e:
    print(json.dumps({"released": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=True))
'@.Replace('PROJ', $proj)
$leaseOut = $leaseCode | & $py - 2>$null | Select-Object -Last 1
$report.lease_release = $leaseOut
Note 'release-lease' $true $leaseOut

# ---------------------------------------------------------------- 6) التشغيل
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$outLog = Join-Path $proj "logs\restart_$stamp.out.log"
$errLog = Join-Path $proj "logs\restart_$stamp.err.log"
New-Item -ItemType Directory -Force -Path (Join-Path $proj 'logs') | Out-Null
$np = Start-Process -FilePath $py `
      -ArgumentList 'scripts\start_node.py', '--port', "$Port" `
      -WorkingDirectory $proj -WindowStyle Hidden `
      -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
Note 'launch' $true "PID $($np.Id) · stdout=$outLog · stderr=$errLog"
$report.new_pid = $np.Id

# ---------------------------------------------------------------- 7) البورت يفتح
$up = $false
for ($i = 0; $i -lt 120; $i++) {
  Start-Sleep -Milliseconds 500
  $lis = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($lis) { $up = $true; break }
}
Note 'port-up' $up "بعد $([math]::Round($i*0.5,1))s"
if (-not $up) {
  $report.aborted = 'port-never-opened'
  $report.launch_out = (Get-Content $outLog -Tail 25 -ErrorAction SilentlyContinue)
  $report.launch_err = (Get-Content $errLog -Tail 25 -ErrorAction SilentlyContinue)
  $report | ConvertTo-Json -Depth 6
  return
}

# البوت رجع قائد؟ (دليل الإقلاع من اللوج)
$botLine = $null
for ($i = 0; $i -lt 60; $i++) {
  $tail = Get-Content (Join-Path $proj 'logs\notebook_v2.log') -Tail 60 -ErrorAction SilentlyContinue
  $botLine = $tail | Where-Object { $_ -like '*القيادة*bot*' -or $_ -like '*@Afkary22Bot*' } |
             Select-Object -Last 1
  if ($botLine) { break }
  Start-Sleep -Milliseconds 500
}
Note 'bot-leader' ([bool]$botLine) ($botLine ?? 'لسه مفيش سطر قيادة في اللوج')

# ---------------------------------------------------------------- 8) قياس «بعد»
Start-Sleep -Seconds 2
$after = [ordered]@{}
foreach ($pth in '/', '/health', '/api/dashboard', '/api/chat') {
  if ($pth -eq '/api/chat') {
    $code = @"
import json, time, urllib.request
req = urllib.request.Request("http://127.0.0.1:$Port/api/chat",
      data=json.dumps({"text":"هاي"}).encode(), headers={"Content-Type":"application/json"})
s = time.time()
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.loads(r.read())
print(json.dumps({"status": r.status, "secs": round(time.time()-s,3),
                  "intent": d.get("intent"), "note_id": d.get("note_id"), "saved": d.get("saved")},
                 ensure_ascii=True))
"@
    $report.after_chat = ($code | & $py - 2>$null | Select-Object -Last 1)
  } else {
    $after[$pth] = (Probe $pth)
  }
}
$report.after = $after

$cmp = [ordered]@{}
foreach ($pth in '/', '/health', '/api/dashboard') {
  $b = $before[$pth]; $a = $after[$pth]
  $cmp[$pth] = [ordered]@{ before = $b.secs; before_status = $b.status
                           after = $a.secs;  after_status = $a.status }
}
$report.compare = $cmp
$report.finished_at = (Get-Date).ToString('HH:mm:ss')
$report | ConvertTo-Json -Depth 6
