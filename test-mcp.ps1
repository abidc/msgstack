$body = @{jsonrpc="2.0";method="tools/list";id=1} | ConvertTo-Json
$request = [System.Net.WebRequest]::Create("http://localhost:8001/mcp")
$request.Method = "POST"
$request.ContentType = "application/json"
$request.Accept = "text/event-stream"
$stream = $request.GetRequestStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.Write($body)
$writer.Close()
$response = $request.GetResponse()
$reader = New-Object System.IO.StreamReader($response.GetResponseStream())
$reader.ReadToEnd()