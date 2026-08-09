# -*- coding: utf-8 -*-
"""HuggingFace 프라이빗 데이터셋 백업 + CDN 검증."""
import os, sys, glob, time, random
import requests
import concurrent.futures as cf
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_log as L, bs_secrets as SEC


def hf_backup(include_raw=True):
    try:
        from huggingface_hub import HfApi, create_repo
    except Exception as e:
        L.warn("huggingface_hub 없음: %s" % e)
        return False
    try:
        token, user = SEC.get("HF_TOKEN"), SEC.get("HF_USER")
    except Exception as e:
        L.warn("HF 시크릿 없음: %s" % e)
        return False
    api = HfApi(token=token)
    targets = [("bluesummer-lora", ST.LORA_OUT, True)]
    if include_raw:
        targets.append(("bluesummer-raw", ST.DIST, False))
    for name, folder, big in targets:
        rid = "%s/%s" % (user, name)
        try:
            create_repo(rid, repo_type="dataset", private=True, token=token,
                        exist_ok=True)
        except Exception as e:
            L.warn("repo 생성 실패 %s: %s" % (rid, e))
            continue
        if not (os.path.isdir(folder) and os.listdir(folder)):
            L.log("건너뜀(비어있음) -> %s" % rid)
            continue
        try:
            if big and hasattr(api, "upload_large_folder"):
                api.upload_large_folder(repo_id=rid, folder_path=folder,
                                        repo_type="dataset")
            else:
                api.upload_folder(folder_path=folder, repo_id=rid,
                                  repo_type="dataset",
                                  commit_message="BLUE SUMMER backup")
            L.ok("HF 업로드 완료 -> %s" % rid)
        except Exception as e:
            L.warn("HF 업로드 실패 %s: %s" % (rid, e))
    try:
        api.upload_folder(folder_path=ST.BASE, repo_id="%s/bluesummer-raw" % user,
                          repo_type="dataset", path_in_repo="_src",
                          commit_message="scripts & state",
                          allow_patterns=["*.py", "seeds.json", "bs_state.json",
                                          "verify_report.json", "*.md"])
        L.ok("스크립트/원장 백업 완료")
    except Exception as e:
        L.warn("스크립트 백업 실패: %s" % e)
    ST.mark("cell12_hf_backup", "done",
            "lora=%d" % len(glob.glob(ST.LORA_OUT + "/*.safetensors")))
    return True


def _probe(url, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=30, allow_redirects=True,
                             headers={"Range": "bytes=0-0"})
            if r.status_code in (200, 206):
                return True
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return False


def cdn_check(full_purge=False, sample=30):
    try:
        user = SEC.get("GITHUB_USER")
    except Exception as e:
        L.warn("GITHUB_USER 없음: %s" % e)
        return []
    base = "https://cdn.jsdelivr.net/gh/%s/bluesummer@main" % user
    st = ST.rescan()
    inv = st["inventory"]
    if full_purge:
        paths = (["c/%s.webp" % x for x in inv["char"]]
                 + ["bg/%s.webp" % x for x in inv["bg"]]
                 + ["ui/%s.webp" % x for x in inv["ui"]])

        def pg(p):
            try:
                requests.get("https://purge.jsdelivr.net/gh/%s/bluesummer@main/%s"
                             % (user, p), timeout=30)
            except Exception:
                pass
        with cf.ThreadPoolExecutor(8) as ex:
            list(ex.map(pg, paths))
        L.log("전량 퍼지 요청 %d건 - 30초 대기" % len(paths))
        time.sleep(30)

    targets = ["%s/ui/%s.webp" % (base, u) for u in inv["ui"]]
    pool = (["c/%s.webp" % x for x in inv["char"]]
            + ["bg/%s.webp" % x for x in inv["bg"]])
    random.shuffle(pool)
    targets += ["%s/%s" % (base, p) for p in pool[:sample]]
    fail = [u for u in targets if not _probe(u)]
    L.log("CDN 검사 %d개 / 실패 %d개" % (len(targets), len(fail)))
    for u in fail[:10]:
        L.warn("   " + u)
    if fail:
        for u in fail:
            try:
                requests.get("https://purge.jsdelivr.net/gh/%s/bluesummer@main/%s"
                             % (user, u.split("@main/", 1)[1]), timeout=30)
            except Exception:
                pass
        time.sleep(20)
        fail = [u for u in fail if not _probe(u, 2)]
        L.log("퍼지 후 남은 실패 %d개" % len(fail))
    ST.mark("cell11_cdn", "done" if not fail else "partial", "fail=%d" % len(fail))
    L.ok("CDN BASE : %s/" % base)
    head = (st.get("last_commit") or "")[:7]
    if head:
        L.log("커밋 고정 주소 : https://cdn.jsdelivr.net/gh/%s/bluesummer@%s/"
              % (user, head))
    return fail
