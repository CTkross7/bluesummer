
# -*- coding: utf-8 -*-
import os, sys, time, json, shutil, subprocess

REPO = "/kaggle/temp/repo"
BASE = "/kaggle/working/BLUESUMMER"
SRC  = os.path.join(BASE, "dist")
LOCK = "/kaggle/temp/bs_git.lock"
SUBS = ("c", "bg", "ui")

sys.path.insert(0, BASE)
import bs_state as ST

def _secrets():
    try:
        with open("/kaggle/temp/bs_env.json", encoding="utf-8") as f:
            s = json.load(f)["secrets"]
        return s.get("GITHUB_USER", ""), s.get("GITHUB_TOKEN", "")
    except Exception:
        pass
    try:
        from kaggle_secrets import UserSecretsClient
        s = UserSecretsClient()
        return s.get_secret("GITHUB_USER").strip(), s.get_secret("GITHUB_TOKEN").strip()
    except Exception:
        return "", ""

def enabled():
    u, t = _secrets()
    return bool(u and t)

def _mask(txt, tok):
    if not txt:
        return ""
    return txt.replace(tok, "*") if tok else txt

def sh(cmd, cwd=REPO, tok="", show=True):
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    if show and out.strip():
        print(_mask(out[-1200:], tok))
    return p.returncode, out

def acquire(timeout=600):
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - t0 > timeout:
                try:
                    os.remove(LOCK)      # 죽은 세션이 남긴 락 회수
                except OSError:
                    pass
                continue
            time.sleep(2)

def release():
    try:
        os.remove(LOCK)
    except OSError:
        pass

def ensure_repo():
    user, tok = _secrets()
    if not (user and tok):
        raise RuntimeError("GitHub 시크릿 없음")
    remote = f"https://{user}:{tok}@github.com/{user}/bluesummer.git"
    os.makedirs("/kaggle/temp", exist_ok=True)
    if not os.path.isdir(os.path.join(REPO, ".git")):
        shutil.rmtree(REPO, ignore_errors=True)
        rc, _ = sh(f"git clone {remote} {REPO}", cwd="/kaggle/temp", tok=tok, show=False)
        if rc != 0 or not os.path.isdir(os.path.join(REPO, ".git")):
            os.makedirs(REPO, exist_ok=True)
            sh("git init -b main", tok=tok, show=False)
            sh(f"git remote add origin {remote}", tok=tok, show=False)
    else:
        sh(f"git remote set-url origin {remote}", tok=tok, show=False)
    sh(f"git config --global --add safe.directory {REPO}", cwd="/kaggle/temp", show=False)
    sh('git config user.email "bluesummer@bot.local"', show=False)
    sh('git config user.name  "bluesummer-bot"', show=False)
    sh("git config core.autocrlf false", show=False)
    sh("git config http.postBuffer 524288000", show=False)
    rc, out = sh("git rev-parse --abbrev-ref HEAD", show=False)
    if rc != 0 or out.strip() != "main":
        sh("git checkout -B main", tok=tok, show=False)
    return user, tok

def copy_assets():
    n = 0
    for sub in SUBS:
        s, d = os.path.join(SRC, sub), os.path.join(REPO, sub)
        if not os.path.isdir(s):
            continue
        os.makedirs(d, exist_ok=True)
        for fn in sorted(os.listdir(s)):
            if not fn.endswith(".webp"):
                continue
            a, b = os.path.join(s, fn), os.path.join(d, fn)
            if (not os.path.exists(b)) or os.path.getsize(a) != os.path.getsize(b):
                shutil.copy2(a, b)
                n += 1
    return n

def copy_meta(include_src=True):
    """원장·인덱스·스크립트를 저장소에 함께 넣어 세션 소멸에 대비."""
    meta = os.path.join(REPO, "_meta")
    os.makedirs(meta, exist_ok=True)
    st = ST.rescan()
    shutil.copy2(ST.PATH, os.path.join(meta, "bs_state.json"))
    idx = {"counts": st["counts"], "updated": st["updated"],
           "char": st["inventory"]["char"], "bg": st["inventory"]["bg"],
           "ui": st["inventory"]["ui"]}
    with open(os.path.join(meta, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    if include_src:
        srcd = os.path.join(REPO, "_src")
        os.makedirs(srcd, exist_ok=True)
        for fn in sorted(os.listdir(BASE)):
            if fn.endswith(".py") or fn in ("seeds.json",):
                shutil.copy2(os.path.join(BASE, fn), os.path.join(srcd, fn))
        for sub in ("dataset_cfg", "toml"):
            p = os.path.join(BASE, sub)
            if os.path.isdir(p):
                shutil.copytree(p, os.path.join(srcd, sub), dirs_exist_ok=True)
    return meta

def sync(message="BLUE SUMMER assets", include_src=True, retries=3):
    if not enabled():
        return {"copied": 0, "head": "", "pushed": False,
                "files_in_repo": 0, "user": "", "dirty": False, "skipped": True}
    acquire()
    try:
        user, tok = ensure_repo()
        copied = copy_assets()
        copy_meta(include_src)
        sh("git add -A", tok=tok, show=False)
        rc, out = sh("git status --porcelain", tok=tok, show=False)
        dirty = bool(out.strip())
        if dirty:
            sh(f'git commit -m "{message}"', tok=tok, show=False)
        pushed = False
        for i in range(retries):
            sh("git fetch origin main", tok=tok, show=False)
            sh("git pull --rebase --autostash origin main", tok=tok, show=False)
            rc, _ = sh("git push origin main", tok=tok, show=(i == retries - 1))
            if rc == 0:
                pushed = True
                break
            sh("git rebase --abort", tok=tok, show=False)
            time.sleep(5)
        rc, out = sh("git rev-parse HEAD", tok=tok, show=False)
        head = out.strip()[:40]
        st = ST.load()
        if head:
            st["last_commit"] = head
            st["commits"] = (st["commits"] + [{"hash": head, "ts": ST._now(),
                                               "msg": message, "pushed": pushed}])[-60:]
        ST.save(st)
        n = sum(len(os.listdir(os.path.join(REPO, s)))
                for s in SUBS if os.path.isdir(os.path.join(REPO, s)))
        return {"copied": copied, "head": head, "pushed": pushed,
                "files_in_repo": n, "user": user, "dirty": dirty, "skipped": False}
    finally:
        release()

def restore(dest=SRC):
    """저장소에서 dist/ 와 _src/ 를 되살린다 (새 세션 복구용)."""
    if not enabled():
        return 0
    acquire()
    try:
        user, tok = ensure_repo()
        sh("git fetch origin main", tok=tok, show=False)
        sh("git reset --hard origin/main", tok=tok, show=False)
        got = 0
        for sub in SUBS:
            s, d = os.path.join(REPO, sub), os.path.join(dest, sub)
            if not os.path.isdir(s):
                continue
            os.makedirs(d, exist_ok=True)
            for fn in sorted(os.listdir(s)):
                a, b = os.path.join(s, fn), os.path.join(d, fn)
                if (not os.path.exists(b)) or os.path.getsize(a) != os.path.getsize(b):
                    shutil.copy2(a, b)
                    got += 1
        srcd = os.path.join(REPO, "_src")
        if os.path.isdir(srcd):
            for fn in sorted(os.listdir(srcd)):
                p = os.path.join(srcd, fn)
                if os.path.isfile(p) and fn not in ("bs_state.py", "bs_git.py",
                                                    "bs_autosave.py"):
                    shutil.copy2(p, os.path.join(BASE, fn))
        meta = os.path.join(REPO, "_meta", "bs_state.json")
        if os.path.exists(meta) and not os.path.exists(ST.PATH):
            shutil.copy2(meta, ST.PATH)
        ST.rescan()
        return got
    finally:
        release()
