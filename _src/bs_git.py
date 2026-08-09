# -*- coding: utf-8 -*-
"""GitHub 동기화. 토큰 마스킹 / 빈 저장소 대응 / pull --rebase 후 push / 파일락.
   자동저장 워커와 20장 단위 푸시가 같은 함수를 쓰므로 충돌하지 않는다."""
import os, sys, time, json, shutil, subprocess

REPO = "/kaggle/temp/repo"
BASE = "/kaggle/working/BLUESUMMER"
SRC  = os.path.join(BASE, "dist")
LOCK = "/kaggle/temp/bs_git.lock"
SUBS = ("c", "bg", "ui")

sys.path.insert(0, BASE)
import bs_state as ST, bs_log as L, bs_secrets as SEC


def _secrets():
    return SEC.get("GITHUB_USER"), SEC.get("GITHUB_TOKEN")


def sh(cmd, cwd=REPO, tok="", show=True):
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    out = SEC.mask((p.stdout or "") + (p.stderr or ""), tok)
    L.write("$ (git) " + SEC.mask(cmd, tok) + "\n" + out)
    if show and out.strip():
        for line in out.strip().splitlines()[-8:]:
            print("   " + line[:200], flush=True)
    return p.returncode, out


def acquire(timeout=900):
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
                    os.remove(LOCK)
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
    remote = "https://%s:%s@github.com/%s/bluesummer.git" % (user, tok, user)
    os.makedirs("/kaggle/temp", exist_ok=True)
    if not os.path.isdir(os.path.join(REPO, ".git")):
        shutil.rmtree(REPO, ignore_errors=True)
        rc, _ = sh("git clone %s %s" % (remote, REPO), cwd="/kaggle/temp", tok=tok, show=False)
        if rc != 0 or not os.path.isdir(os.path.join(REPO, ".git")):
            os.makedirs(REPO, exist_ok=True)
            sh("git init -b main", tok=tok, show=False)
            sh("git remote add origin %s" % remote, tok=tok, show=False)
    else:
        sh("git remote set-url origin %s" % remote, tok=tok, show=False)
    sh("git config --global --add safe.directory %s" % REPO, cwd="/kaggle/temp", show=False)
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
            if fn.endswith((".py", ".md")) or fn in ("seeds.json", "verify_report.json"):
                try:
                    shutil.copy2(os.path.join(BASE, fn), os.path.join(srcd, fn))
                except Exception:
                    pass
        for sub in ("lora/_config",):
            p = os.path.join(BASE, sub)
            if os.path.isdir(p):
                shutil.copytree(p, os.path.join(srcd, "lora_config"), dirs_exist_ok=True)
    return meta


def flag_path(name):
    return os.path.join(REPO, "_meta", name)


def has_flag(name):
    """원격 저장소에 남긴 영구 표식 확인 (세션이 사라져도 유지된다)."""
    try:
        acquire()
        ensure_repo()
        sh("git fetch origin main", show=False)
        sh("git reset --hard origin/main", show=False)
        return os.path.exists(flag_path(name))
    except Exception as e:
        L.warn("flag 확인 실패(%s) - 없음으로 간주" % e)
        return False
    finally:
        release()


def set_flag(name, text=""):
    try:
        acquire()
        user, tok = ensure_repo()
        os.makedirs(os.path.join(REPO, "_meta"), exist_ok=True)
        with open(flag_path(name), "w", encoding="utf-8") as f:
            f.write(text or ST._now())
        sh("git add -A", tok=tok, show=False)
        sh('git commit -m "flag %s"' % name, tok=tok, show=False)
        for i in range(3):
            sh("git pull --rebase --autostash origin main", tok=tok, show=False)
            rc, _ = sh("git push origin main", tok=tok, show=False)
            if rc == 0:
                return True
            time.sleep(4)
        return False
    finally:
        release()


def sync(message="BLUE SUMMER assets", include_src=True, retries=3):
    acquire()
    try:
        user, tok = ensure_repo()
        copied = copy_assets()
        copy_meta(include_src)
        sh("git add -A", tok=tok, show=False)
        rc, out = sh("git status --porcelain", tok=tok, show=False)
        if out.strip():
            sh('git commit -m "%s"' % message.replace('"', "'"), tok=tok, show=False)
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
                "files_in_repo": n, "user": user}
    finally:
        release()


def restore(dest=SRC, assets=True):
    """저장소에서 에셋과 데이터 파일만 되살린다.
       파이썬 모듈(.py)은 노트북이 매 세션 새로 쓰므로 절대 덮어쓰지 않는다."""
    acquire()
    try:
        user, tok = ensure_repo()
        sh("git fetch origin main", tok=tok, show=False)
        sh("git reset --hard origin/main", tok=tok, show=False)
        got = 0
        if assets:
            for sub in SUBS:
                s, d = os.path.join(REPO, sub), os.path.join(dest, sub)
                if not os.path.isdir(s):
                    continue
                os.makedirs(d, exist_ok=True)
                for fn in sorted(os.listdir(s)):
                    if not fn.endswith(".webp"):
                        continue
                    a, b = os.path.join(s, fn), os.path.join(d, fn)
                    if (not os.path.exists(b)) or os.path.getsize(a) != os.path.getsize(b):
                        shutil.copy2(a, b)
                        got += 1
        srcd = os.path.join(REPO, "_src")
        if os.path.isdir(srcd):
            for fn in ("seeds.json", "verify_report.json"):
                p = os.path.join(srcd, fn)
                if os.path.exists(p) and not os.path.exists(os.path.join(BASE, fn)):
                    shutil.copy2(p, os.path.join(BASE, fn))
        meta = os.path.join(REPO, "_meta", "bs_state.json")
        if os.path.exists(meta) and not os.path.exists(ST.PATH):
            shutil.copy2(meta, ST.PATH)
        ST.rescan()
        return got
    finally:
        release()
