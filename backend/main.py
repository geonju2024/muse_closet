from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

CATEGORIES = {"tops": "상의", "bottoms": "하의", "outerwear": "아우터"}
DEFAULT_DB = Path(__file__).parent / "closet.db"

class PredictionIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    category: Literal["tops", "bottoms", "outerwear"]
    confidence: float = Field(ge=0, le=1)
    inference_ms: float = Field(ge=0)
    model_version: str = Field(default="v1", max_length=40)

def create_app(db_path: Path | None = None) -> FastAPI:
    path = Path(db_path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="MUSE Closet Vision API")

    def connection():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        return db

    with connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS prediction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                device_id TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                inference_ms REAL NOT NULL,
                model_version TEXT NOT NULL
            )
        """)

    @app.get('/health')
    def health():
        return {"ok": True}

    @app.post('/api/predictions', status_code=201)
    def save_prediction(p: PredictionIn):
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with connection() as db:
            cursor = db.execute("""
                INSERT INTO prediction_logs
                (created_at, device_id, category, confidence, inference_ms, model_version)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, p.device_id, p.category, p.confidence,
                  p.inference_ms, p.model_version))
            row_id = cursor.lastrowid
        return {"id": row_id, "created_at": now, "saved": True}

    @app.get('/api/predictions')
    def list_predictions(limit: int = 50):
        limit = max(1, min(limit, 200))
        with connection() as db:
            rows = db.execute("""
                SELECT * FROM prediction_logs ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    @app.get('/', response_class=HTMLResponse)
    def dashboard():
        return """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MUSE Closet Vision</title>
<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:35px auto;padding:0 18px;background:#f7f8fa;color:#172026}
h1{margin-bottom:4px}small{color:#64748b}table{border-collapse:collapse;width:100%;background:white;margin-top:24px}
th,td{padding:11px;border-bottom:1px solid #e5e7eb;text-align:left}th{background:#edf2f6}
.pill{border-radius:12px;background:#dcefe7;padding:3px 9px}</style></head>
<body><h1>MUSE Closet Vision</h1><small>ESP32-S3 의류 분류 로그 · 5초마다 새로고침</small>
<p id="count">로그를 불러오는 중...</p><table><thead><tr>
<th>시각(UTC)</th><th>분류</th><th>신뢰도</th><th>추론(ms)</th><th>장치</th>
</tr></thead><tbody id="rows"></tbody></table>
<script>
const labels={tops:'상의',bottoms:'하의',outerwear:'아우터'};
async function load(){try{
 const r=await fetch('/api/predictions');if(!r.ok)throw new Error(r.status);
 const data=await r.json();
 document.querySelector('#count').textContent=`최근 ${data.length}개 추론 기록`;
 const tbody=document.querySelector('#rows');tbody.replaceChildren();
 data.forEach(p=>{const tr=document.createElement('tr');
 [p.created_at,labels[p.category]||p.category,(p.confidence*100).toFixed(1)+'%',
 p.inference_ms.toFixed(1),p.device_id].forEach((v,i)=>{
   const td=document.createElement('td');td.textContent=v;
   if(i===1)td.className='pill';tr.appendChild(td);
 });tbody.appendChild(tr);});
 }catch(e){document.querySelector('#count').textContent='서버 데이터 조회 실패: '+e;}}
load();setInterval(load,5000);
</script></body></html>"""
    return app

app = create_app()
