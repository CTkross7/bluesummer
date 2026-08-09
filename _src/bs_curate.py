
# -*- coding: utf-8 -*-
import os, sys, glob, shutil, json
import numpy as np
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST

CAND = os.path.join(ST.BASE, "lora_src", "candidates")
SEL  = os.path.join(ST.BASE, "lora_src", "selected")
KEEP = 20

def _sharpness(path):
    from PIL import Image
    im = Image.open(path).convert("L").resize((256, 384))
    a = np.asarray(im, dtype=np.float32)
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    lap = np.zeros_like(a)
    lap[1:-1, 1:-1] = sum(
        k[i + 1, j + 1] * a[1 + i:a.shape[0] - 1 + i, 1 + j:a.shape[1] - 1 + j]
        for i in (-1, 0, 1) for j in (-1, 0, 1) if k[i + 1, j + 1] != 0)
    return float(lap.var())

def _app():
    try:
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l",
                           providers=["CUDAExecutionProvider",
                                      "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        return app
    except Exception as e:
        print("  insightface 불가 → 선명도 기준 폴백:", e)
        return None

def run(chars=None, keep=KEEP):
    import cv2
    chars = chars or ST.CHARS
    app = _app()
    for c in chars:
        src = os.path.join(CAND, c)
        dst = os.path.join(SEL, c)
        if not os.path.isdir(src):
            print(f"{c}: 후보 없음 — 건너뜀")
            continue
        if len(glob.glob(dst + "/*.png")) >= min(keep, 12):
            print(f"{c}: 이미 선별됨")
            continue
        os.makedirs(dst, exist_ok=True)
        files = sorted(glob.glob(src + "/*.png"))
        rows = []
        for f in files:
            s = _sharpness(f)
            emb, nface = None, 1
            if app is not None:
                img = cv2.imread(f)
                faces = app.get(img) if img is not None else []
                nface = len(faces)
                if nface == 1:
                    emb = faces[0].normed_embedding
            rows.append({"f": f, "s": s, "n": nface, "e": emb})
        pool = [r for r in rows if r["n"] == 1] or rows
        if app is not None and all(r["e"] is not None for r in pool) and len(pool) > 3:
            M = np.stack([r["e"] for r in pool])
            sim = M @ M.T
            med = M[int(np.argmax(sim.mean(1)))]
            for r in pool:
                r["score"] = float(r["e"] @ med) * 100 + min(r["s"], 400) / 400 * 10
        else:
            for r in pool:
                r["score"] = min(r["s"], 400) / 400 * 10
        pool.sort(key=lambda r: -r["score"])
        chosen = pool[:keep]
        for i, r in enumerate(chosen):
            shutil.copy2(r["f"], os.path.join(dst, f"{c}_{i:02d}.png"))
        print(f"{c}: {len(files)}장 중 {len(chosen)}장 선별 "
              f"(평균점수 {np.mean([r['score'] for r in chosen]):.1f})")
        ST.mark(f"curate_{c}", "done", str(len(chosen)))
    return True
