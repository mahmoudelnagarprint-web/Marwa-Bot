# Local OCR via the Windows built-in engine (Windows.Media.Ocr).
# Fully offline: no internet, no API keys, no pip installs.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File win_ocr.ps1 -Path "image.png" [-Lang ar-SA]
# NOTE: keep this file ASCII-only; Windows PowerShell 5.1 misreads non-ASCII source without a BOM.
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$Lang = 'ar-SA'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Path)) { Write-Error "file not found: $Path"; exit 2 }

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

# await bridge for WinRT async calls from PowerShell 5.1
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
function Await($task, $type) {
    $m = $asTaskGeneric.MakeGenericMethod($type)
    $t = $m.Invoke($null, @($task))
    $t.Wait(-1) | Out-Null
    $t.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$language = New-Object Windows.Globalization.Language($Lang)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) { Write-Error "no OCR engine available for language $Lang"; exit 3 }

$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

Write-Output ("=== OCR engine=" + $engine.RecognizerLanguage.LanguageTag + " size=" + $bitmap.PixelWidth + "x" + $bitmap.PixelHeight + " ===")
foreach ($line in $result.Lines) {
    $r = $line.Words[0].BoundingRect
    $x = [int]$r.X
    $y = [int]$r.Y
    Write-Output ("[" + $x + "," + $y + "] " + $line.Text)
}
Write-Output ("=== end lines=" + $result.Lines.Count + " ===")
