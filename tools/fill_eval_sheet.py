"""평가 15회가 끝난 뒤 실행: DB의 실제 ESP32 추론 로그를 eval_sheet.csv와 대조해 결과표 생성.

사용 (서버가 켜진 상태에서, 프로젝트 루트):
  py tools/fill_eval_sheet.py                 # 최근 로그 15건을 trial 1..15에 순서대로 매칭
  py tools/fill_eval_sheet.py --first-id 3    # DB id 3부터를 trial 1로 매칭(시험 기록 제외 시)

출력: data/eval/eval_sheet.csv 갱신, docs/eval_results.md 생성(README에 붙여넣기용)
"""
import argparse, csv, json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "eval" / "eval_sheet.csv"
OUT_MD = ROOT / "docs" / "eval_results.md"
CLASSES = ["tops", "bottoms", "outerwear"]
KO = {"tops": "상의", "bottoms": "하의", "outerwear": "아우터"}

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://127.0.0.1:8000/api/predictions?limit=200")
ap.add_argument("--first-id", type=int, default=None, help="trial 1에 해당하는 DB id")
ap.add_argument("--model-version", default="ei-1.0.1", help="이 값의 로그만 사용(데모 데이터 제외)")
args = ap.parse_args()

with open(SHEET, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
logs = sorted(json.load(urlopen(args.api, timeout=5)), key=lambda r: r["id"])
logs = [r for r in logs if r["model_version"] == args.model_version]
if args.first_id is not None:
    logs = [r for r in logs if r["id"] >= args.first_id][: len(rows)]
else:
    logs = logs[-len(rows):]
if len(logs) < len(rows):
    raise SystemExit(f"DB에 '{args.model_version}' 로그가 {len(logs)}건뿐입니다. 평가 {len(rows)}회를 먼저 완료하세요.")

for row, log in zip(rows, logs):
    row.update(pred=log["category"], confidence=f'{log["confidence"]:.4f}',
               inference_ms=f'{log["inference_ms"]:.0f}', db_id=log["id"],
               correct="O" if log["category"] == row["truth"] else "X")
with open(SHEET, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n = len(rows)
ok = sum(r["correct"] == "O" for r in rows)
ms = [float(r["inference_ms"]) for r in rows]
lines = ["| # | 정답 | 예측 | 신뢰도 | 추론(ms) | DB id | 결과 |", "|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(f'| {r["trial"]} | {KO[r["truth"]]} | {KO.get(r["pred"], r["pred"])} | '
                 f'{float(r["confidence"]):.2f} | {r["inference_ms"]} | {r["db_id"]} | {r["correct"]} |')
lines += ["", "| 클래스 | 정답/시도 | 정확도 |", "|---|---|---|"]
for c in CLASSES:
    sub = [r for r in rows if r["truth"] == c]
    k = sum(r["correct"] == "O" for r in sub)
    lines.append(f"| {KO[c]} ({c}) | {k}/{len(sub)} | {k / len(sub) * 100:.0f}% |")
lines.append(f"| **전체** | **{ok}/{n}** | **{ok / n * 100:.0f}%** |")
lines += ["", f"평균 추론 시간(DSP+NN, ESP32-S3): **{sum(ms) / n:.0f} ms** (최소 {min(ms):.0f} / 최대 {max(ms):.0f})"]
cm = {t: {p: 0 for p in CLASSES} for t in CLASSES}
for r in rows:
    if r["pred"] in CLASSES:
        cm[r["truth"]][r["pred"]] += 1
lines += ["", "혼동 행렬 (행=정답, 열=예측)", "", "| | " + " | ".join(KO[c] for c in CLASSES) + " |",
          "|---" * (len(CLASSES) + 1) + "|"]
for t in CLASSES:
    lines.append(f"| {KO[t]} | " + " | ".join(str(cm[t][p]) for p in CLASSES) + " |")
OUT_MD.parent.mkdir(exist_ok=True)
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\n저장: {SHEET}\n저장: {OUT_MD}")
