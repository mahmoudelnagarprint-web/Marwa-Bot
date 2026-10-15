param(
    [string]$FilePath
)

try {
    if (-not (Test-Path $FilePath)) {
        Write-Error "File not found: $FilePath"
        exit 1
    }

    # Load Windows Forms
    Add-Type -AssemblyName System.Windows.Forms
    
    # Create StringCollection
    $fileList = New-Object System.Collections.Specialized.StringCollection
    $fileList.Add($FilePath)
    
    # Set to Clipboard
    [System.Windows.Forms.Clipboard]::SetFileDropList($fileList)
    Start-Sleep -Milliseconds 200
    [System.Windows.Forms.Clipboard]::Flush()
    
    Write-Host "Success"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
