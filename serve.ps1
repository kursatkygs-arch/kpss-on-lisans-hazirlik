$port = 5588
$root = $PSScriptRoot
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()

Write-Host "KPSS uygulaması çalışıyor: http://localhost:$port/"
Write-Host "Kapatmak için bu pencereyi kapatabilir ya da Ctrl+C yapabilirsin."
Start-Process "http://localhost:$port/index.html"

$contentTypes = @{
  ".html" = "text/html; charset=utf-8"
  ".js"   = "application/javascript"
  ".css"  = "text/css"
  ".json" = "application/json"
  ".png"  = "image/png"
  ".jpg"  = "image/jpeg"
  ".jpeg" = "image/jpeg"
  ".svg"  = "image/svg+xml"
  ".ico"  = "image/x-icon"
}

while ($listener.IsListening) {
  try {
    $context = $listener.GetContext()
  } catch {
    break
  }
  $request = $context.Request
  $response = $context.Response
  $localPath = $request.Url.LocalPath
  if ($localPath -eq "/") { $localPath = "/index.html" }
  $filePath = Join-Path $root ($localPath.TrimStart('/'))
  $fullRoot = (Resolve-Path $root).Path
  $resolved = $null
  if (Test-Path $filePath -PathType Leaf) {
    $resolved = (Resolve-Path $filePath).Path
  }
  if ($resolved -and $resolved.StartsWith($fullRoot)) {
    $bytes = [System.IO.File]::ReadAllBytes($resolved)
    $ext = [System.IO.Path]::GetExtension($resolved).ToLower()
    $contentType = $contentTypes[$ext]
    if (-not $contentType) { $contentType = "application/octet-stream" }
    $response.ContentType = $contentType
    $response.ContentLength64 = $bytes.Length
    $response.OutputStream.Write($bytes, 0, $bytes.Length)
  } else {
    $response.StatusCode = 404
  }
  $response.OutputStream.Close()
}
