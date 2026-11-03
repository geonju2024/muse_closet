"""데이터 육안 검수용 썸네일 시트 생성: py contact_sheet.py <ei_upload 폴더> <출력 폴더>
각 칸에 번호를 붙여 시트 단위로 확인 → 잘못된 사진은 index.txt에서 파일명을 찾아 삭제."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
COLS, ROWS, T = 8, 6, 150
OUT.mkdir(parents=True, exist_ok=True)
for cat in ("tops", "bottoms", "outerwear"):
    files = sorted(SRC.glob(f"*/{cat}.*.jpg"))
    lines = []
    for s in range(0, len(files), COLS * ROWS):
        chunk = files[s:s + COLS * ROWS]
        sheet = Image.new("RGB", (COLS * T, ROWS * T), "white")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(chunk):
            im = Image.open(f).convert("RGB")
            im.thumbnail((T - 4, T - 4))
            x, y = (i % COLS) * T, (i // COLS) * T
            sheet.paste(im, (x + 2, y + 2))
            n = s + i
            d.rectangle([x + 2, y + 2, x + 34, y + 16], fill="black")
            d.text((x + 4, y + 3), str(n), fill="yellow")
            lines.append(f"{n}\t{f.relative_to(SRC)}")
        sheet.save(OUT / f"{cat}_{s // (COLS * ROWS):02d}.jpg", quality=85)
    (OUT / f"{cat}_index.txt").write_text("\n".join(lines), encoding="utf-8")
    print(cat, len(files))
