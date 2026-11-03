"""clothing-dataset-small -> Edge Impulse upload folders (tops/bottoms/outerwear, balanced)."""
import random, shutil, sys
from pathlib import Path

SRC = Path(sys.argv[1])
DST = Path(sys.argv[2])
MAP = {
    "tops": ["t-shirt", "shirt", "longsleeve"],
    "bottoms": ["pants", "shorts", "skirt"],
    "outerwear": ["outwear"],
}
N_TRAIN, N_TEST = 128, 32  # 클래스당 160장 x 3 = 480장 목표
rng = random.Random(42)

def pick(splits, subs, n):
    per = {s: sorted(p for sp in splits for p in (SRC / sp / s).glob("*.jpg")) for s in subs}
    for v in per.values():
        rng.shuffle(v)
    out, i = [], 0
    while len(out) < n:  # 하위 클래스에서 번갈아 뽑아 고르게 섞음
        s = subs[i % len(subs)]
        if per[s]:
            out.append((s, per[s].pop()))
        i += 1
    return out

if DST.exists():
    shutil.rmtree(DST)
for cat, subs in MAP.items():
    for folder, splits, n in (("training", ["train", "validation"], N_TRAIN), ("testing", ["test"], N_TEST)):
        d = DST / folder
        d.mkdir(parents=True, exist_ok=True)
        for sub, p in pick(splits, subs, n):
            shutil.copy2(p, d / f"{cat}.{sub}_{p.stem}.jpg")
for folder in ("training", "testing"):
    files = list((DST / folder).glob("*.jpg"))
    counts = {c: sum(f.name.startswith(c + ".") for f in files) for c in MAP}
    print(folder, len(files), counts)
