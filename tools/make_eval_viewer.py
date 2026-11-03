"""시연·평가용 이미지 세트와 전체화면 뷰어 생성.
학습(training)·테스트(testing)·제외(rejected) 어디에도 쓰이지 않은 원본 이미지에서 클래스당 N장 선택.
사용: py tools/make_eval_viewer.py <clothing-dataset-small> <data 폴더> [클래스당 장수=5]"""
import csv, json, random, shutil, sys
from pathlib import Path

SRC, DATA = Path(sys.argv[1]), Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 5
MAP = {"tops": ["t-shirt", "shirt", "longsleeve"],
       "bottoms": ["pants", "shorts", "skirt"],
       "outerwear": ["outwear"]}
rng = random.Random(7)
EXCLUDE = {"6228decd-43bc-4048-ad5c-507211352beb", "b167f39f-eea8-4f69-9494-e2346bd7e2c5"}  # 육안 검수로 제외(아기 우주복, 전신 스노우슈트)

used = {p.name.split(".", 1)[1].split("_", 1)[1].rsplit(".", 1)[0]
        for d in ("ei_upload", "rejected") for p in (DATA / d).rglob("*.jpg")}
out = DATA / "eval"
if out.exists():
    shutil.rmtree(out)
(out / "img").mkdir(parents=True)

items = []
for cat, subs in MAP.items():
    per = {s: [p for sp in ("train", "validation", "test")
               for p in sorted((SRC / sp / s).glob("*.jpg")) if p.stem not in used | EXCLUDE] for s in subs}
    for v in per.values():
        rng.shuffle(v)
    pool = [(subs[k % len(subs)], per[subs[k % len(subs)]][k // len(subs)])
            for k in range(N)]  # 하위 클래스(셔츠/티/긴팔, 바지/반바지/치마)를 번갈아 선택
    for i, (sub, p) in enumerate(pool):
        name = f"{cat}_{i + 1:02d}.jpg"
        shutil.copy2(p, out / "img" / name)
        items.append({"file": f"img/{name}", "truth": cat, "source": f"{sub}/{p.name}"})
rng.shuffle(items)  # 시연 순서를 섞어 클래스가 번갈아 나오게
for i, it in enumerate(items, 1):
    it["trial"] = i

with open(out / "eval_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["trial", "file", "truth", "pred", "confidence", "inference_ms", "db_id", "correct", "source"])
    for it in items:
        w.writerow([it["trial"], it["file"], it["truth"], "", "", "", "", "", it["source"]])

html = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>Closet Eval Viewer</title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}
img{width:100vw;height:100vh;object-fit:contain;display:block}
#info{position:fixed;left:12px;bottom:10px;font:14px monospace;color:#888;display:none}
#help{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;color:#ccc;font:18px sans-serif;text-align:center;background:#000}</style></head>
<body><img id="im" alt=""><div id="info"></div>
<div id="help">사진 클릭 또는 → 다음 &nbsp;·&nbsp; ← 이전 &nbsp;·&nbsp; F 전체화면 &nbsp;·&nbsp; I 정답/번호 표시 토글<br><br>클릭하거나 아무 키나 눌러 시작</div>
<script>
const items=__ITEMS__;let i=0;
const im=document.getElementById('im'),info=document.getElementById('info'),help=document.getElementById('help');
function show(){const it=items[i];im.src=it.file;info.textContent=`trial ${it.trial}/${items.length} · truth: ${it.truth} · ${it.file}`;}
document.addEventListener('keydown',e=>{help.style.display='none';
 if(e.key==='ArrowRight'||e.key===' ')i=Math.min(items.length-1,i+1);
 else if(e.key==='ArrowLeft')i=Math.max(0,i-1);
 else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();}
 else if(e.key==='i'||e.key==='I'){info.style.display=info.style.display==='block'?'none':'block';}
 show();});
im.addEventListener('click',()=>{help.style.display='none';i=Math.min(items.length-1,i+1);show();});
help.addEventListener('click',()=>{help.style.display='none';});
show();
</script></body></html>""".replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
(out / "viewer.html").write_text(html, encoding="utf-8")
print(f"{len(items)} images -> {out}")
for it in items:
    print(it["trial"], it["truth"], it["source"])
