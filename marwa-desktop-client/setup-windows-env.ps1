# ============================================================
#  MARWA CORE — إعداد بيئة سطح المكتب على ويندوز
#  تثبيت Rust + C++ Build Tools بصمت عبر winget
#  يعمل على عقدة الورشة وعقدة اللابتوب — بأمر المالك 2026-10-26
# ============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

function Show-Step($msg) { Write-Host "`n[$([DateTime]::Now.ToString('HH:mm:ss'))] $msg" -ForegroundColor Cyan }
function Show-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Show-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host ''
Write-Host '════════════════════════════════════════════════' -ForegroundColor DarkGray
Write-Host '  مروة كور — إعداد بيئة سطح المكتب (Tauri Shell)' -ForegroundColor Gold
Write-Host '  تثبيت: أدوات بناء ++C + لغة Rust — صامت عبر winget' -ForegroundColor Gray
Write-Host '════════════════════════════════════════════════' -ForegroundColor DarkGray

# ── 1) رفع صلاحيات المسؤول تلقائياً ──────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Host ''
  Show-Warn 'السكربت يحتاج صلاحيات المسؤول — راجع نافذة تأكيد ويندوز (UAC) واضغط نعم'
  try {
    Start-Process -FilePath 'powershell.exe' -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit 0
  } catch {
    Write-Host '  ✗ لم تُمنح صلاحيات المسؤول — لا يمكن المتابعة' -ForegroundColor Red
    Read-Host 'اضغط Enter للإغلاق'
    exit 1
  }
}
Show-Ok 'صلاحيات المسؤول ممنوحة'

# ── 2) التأكد من توفر winget ────────────────────────────────
Show-Step 'فحص أداة winget'
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Write-Host '  ✗ winget غير متوفر — ثبّت "App Installer" من متجر مايكروسوفت ثم أعد التشغيل' -ForegroundColor Red
  Read-Host 'اضغط Enter للإغلاق'
  exit 1
}
Show-Ok "winget جاهز — $((winget --version) 2>$null)"

# ── 3) أدوات بناء ++C من مايكروسوفت (الرابط الأساسي لـTauri) ──
Show-Step 'الخطوة 1 من 2: تثبيت Microsoft C++ Build Tools (تنزيل كبير ~2GB — صبر قليل)'
Show-Warn 'لو ظهرت نافذة تثبيت بصرية فهي تكمّل تلقائياً — لا تغلقها'
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
if ($LASTEXITCODE -eq 0) { Show-Ok 'أدوات بناء ++C اكتملت' }
else { Show-Warn "خرج winget بالكود $LASTEXITCODE (لو كان مثبتاً من قبل فده طبيعي — نكمل)" }

# ── 4) لغة Rust عبر rustup ──────────────────────────────────
Show-Step 'الخطوة 2 من 2: تثبيت لغة Rust (rustup)'
winget install --id Rustlang.Rustup -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -eq 0) { Show-Ok 'rustup اكتمل' }
else { Show-Warn "خرج winget بالكود $LASTEXITCODE (لو كان مثبتاً من قبل فده طبيعي — نكمل)" }

# ── 5) تفعيل cargo في هذه الجلسة + سلسلة stable ─────────────
Show-Step 'تجهيز سلسلة Rust الافتراضية'
$env:Path += ";$env:USERPROFILE\.cargo\bin"
if (Get-Command cargo -ErrorAction SilentlyContinue) {
  Show-Ok "cargo موجود: $((cargo --version) 2>$null)"
} else {
  Show-Warn 'cargo لم يُعثر عليه بعد — تشغيل rustup لتنزيل سلسلة stable-msvc (دقائق قليلة)'
  & "$env:USERPROFILE\.cargo\bin\rustup.exe" default stable-msvc 2>$null
  if (-not $?) { rustup default stable-msvc 2>$null }
}
$env:Path += ";$env:USERPROFILE\.cargo\bin"
if (Get-Command cargo -ErrorAction SilentlyContinue) {
  Show-Ok "سلسلة Rust جاهزة: $((rustc --version) 2>$null)"
} else {
  Show-Warn 'اقفل وافتح Terminal جديد ثم جرّب: cargo --version (تحديث الـPATH يحتاج جلسة جديدة)'
}

# ── 6) الخلاصة ───────────────────────────────────────────────
Write-Host ''
Write-Host '════════════════════════════════════════════════' -ForegroundColor DarkGray
Write-Host '  انتهى الإعداد — خطوة التشغيل النهائية:' -ForegroundColor Gold
Write-Host '  cd "G:\ai\Naggar Print POS Agent\marwa-desktop-client"' -ForegroundColor White
Write-Host '  pnpm tauri dev' -ForegroundColor White
Write-Host '  (أول تشغيل يكومبايل Rust 5-15 دقيقة — مرة واحدة بس)' -ForegroundColor Gray
Write-Host '════════════════════════════════════════════════' -ForegroundColor DarkGray
Read-Host 'اضغط Enter للإغلاق'