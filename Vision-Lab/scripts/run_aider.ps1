# ============================================================================
# Vision-Lab — مشغل Aider الجاهز | عقدة اللابتوب (LAPTOP_NODE) | 2026-10-17
# ----------------------------------------------------------------------------
# الاستخدام (من أي مكان):
#   powershell -ExecutionPolicy Bypass -File G:\Marwa-Bot\Vision-Lab\scripts\run_aider.ps1 --message "..." [ملفات...]
#   كل الوسائط الإضافية تُمرَّر إلى Aider كما هي.
#   (ملاحظة: سياسة التنفيذ على اللابتوب تمنع ملفات .ps1 افتراضياً — Bypass على
#    مستوى الأمر/العملية يكفي ولا يغير أي إعداد نظام دائم.)
#
# ماذا يفعل؟
#   1) يقرأ DAHL_API_KEY من .env الخاصة بجذر المستودع (خارج المعمل وخارج Git).
#   2) يضعها في متغير البيئة OPENAI_API_KEY لعملية Aider الحالية فقط.
#   3) يشغّل aider من بيئة المعمل المعزولة (.venv-aider) مع config/aider.config.yml.
#
# قاعدة أمنية صارمة: المفتاح لا يُطبع ولا يُكتب داخل Vision-Lab إطلاقاً.
# ============================================================================

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AiderArgs
)

$ErrorActionPreference = 'Stop'
$labRoot  = Split-Path -Parent $PSScriptRoot            # Vision-Lab
$repoRoot = Split-Path -Parent $labRoot                 # Marwa-Bot
$repoEnv  = Join-Path $repoRoot '.env'
$aiderCfg = Join-Path $labRoot 'config\aider.config.yml'
$aiderExe = Join-Path $labRoot '.venv-aider\Scripts\aider.exe'

foreach ($p in @($repoEnv, $aiderCfg, $aiderExe)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw "[run_aider.ps1] مطلوب وغير موجود: $p (شغّل تهيئة المعمل أولاً)"
    }
}

# --- قراءة المفتاح من .env (صامتة تماماً — لا يُعاد طباعته أبداً) ----------
$key = $null
foreach ($line in Get-Content -LiteralPath $repoEnv -Encoding UTF8) {
    if ($line -match '^\s*DAHL_API_KEY\s*=\s*"?([^"\r\n]+)"?\s*$') {
        $key = $Matches[1].Trim()
        break
    }
}
if (-not $key) { throw "[run_aider.ps1] DAHL_API_KEY غير موجود في .env الخاصة بالمستودع" }

$env:OPENAI_API_KEY  = $key
$env:OPENAI_API_BASE = 'https://inference.dahl.global/v1'

Write-Host ("[run_aider.ps1] تم تحميل مفتاح DAHL من .env (طول المفتاح {0} حرفاً — لن يُعرض هنا). إطلاق Aider..." -f $key.Length)

Set-Location -LiteralPath $labRoot
& $aiderExe --config $aiderCfg @AiderArgs
exit $LASTEXITCODE
