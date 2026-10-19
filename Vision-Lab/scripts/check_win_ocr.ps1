# فحص محرك OCR المدمج في ويندوز (Windows.Media.Ocr) — لغات التعرف المتاحة
# يُشغَّل بـ: powershell -NoProfile -ExecutionPolicy Bypass -File check_win_ocr.ps1
$ErrorActionPreference = 'Stop'
try {
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
    Write-Output ("AvailableRecognizerLanguages count = " + $langs.Count)
    foreach ($l in $langs) { Write-Output ("  - " + $l.LanguageTag + "  (" + $l.DisplayName + ")") }
    $max = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
    Write-Output ("MaxImageDimension = " + $max)
} catch {
    Write-Output ("WinRT OCR unavailable: " + $_.Exception.Message)
}
