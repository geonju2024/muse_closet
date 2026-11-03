"""서버가 켜진 상태에서 실행: python send_demo.py"""
import json
from urllib.request import Request, urlopen

body = {
    'device_id':'xiao-esp32s3-01',
    'category':'tops',
    'confidence':0.91,
    'inference_ms':150.0,
    'model_version':'demo'
}
request = Request('http://127.0.0.1:8000/api/predictions',
                  data=json.dumps(body).encode(),
                  headers={'Content-Type':'application/json'}, method='POST')
with urlopen(request, timeout=5) as response:
    print('API response:', response.read().decode())
