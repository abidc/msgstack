import requests
r = requests.post('http://localhost:8001/mcp',
    json={'jsonrpc': '2.0', 'method': 'initialize', 'id': 1,
          'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                    'clientInfo': {'name': 'test', 'version': '1.0'},
                    'sessionId': 'test-123'}})
print('Init:', r.text[:500])

r2 = requests.post('http://localhost:8001/mcp',
    json={'jsonrpc': '2.0', 'method': 'tools/list', 'id': 2,
          'params': {'sessionId': 'test-123'}})
print('Tools:', r2.text[:1500])