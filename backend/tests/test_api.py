from fastapi.testclient import TestClient
from main import create_app

def test_save_and_read_prediction(tmp_path):
    app = create_app(tmp_path / 'test.db')
    client = TestClient(app)
    data = {
        'device_id': 'xiao-esp32s3-01',
        'category': 'tops',
        'confidence': 0.91,
        'inference_ms': 120.0,
        'model_version': 'v1'
    }
    response = client.post('/api/predictions', json=data)
    assert response.status_code == 201
    assert response.json()['saved'] is True
    rows = client.get('/api/predictions').json()
    assert len(rows) == 1
    assert rows[0]['category'] == 'tops'
    assert rows[0]['confidence'] == 0.91

def test_reject_invalid_class(tmp_path):
    client = TestClient(create_app(tmp_path / 'test.db'))
    r = client.post('/api/predictions', json={
        'device_id':'xiao', 'category':'sneakers',
        'confidence':0.9,'inference_ms':100
    })
    assert r.status_code == 422

def test_health(tmp_path):
    client = TestClient(create_app(tmp_path / 'test.db'))
    assert client.get('/health').json() == {'ok': True}
