# -*- coding: utf-8 -*-
"""Kaggle Secrets -> 환경변수 순으로 자격증명을 찾는다 (Colab 등에서도 동작)."""
import os, sys
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_log as L

KEYS = ["CIVITAI_TOKEN", "GITHUB_TOKEN", "GITHUB_USER", "HF_TOKEN", "HF_USER"]
_CACHE = {}


def get(key, required=True, default=None):
    if key in _CACHE:
        return _CACHE[key]
    val = None
    try:
        from kaggle_secrets import UserSecretsClient
        val = UserSecretsClient().get_secret(key)
    except Exception:
        val = None
    if not val:
        val = os.environ.get(key)
    if val:
        val = val.strip()
        _CACHE[key] = val
        return val
    if required:
        raise RuntimeError("시크릿 '%s' 없음 - Add-ons > Secrets 에 등록하세요" % key)
    return default


def has(key):
    try:
        return bool(get(key, required=False))
    except Exception:
        return False


def check_all(verbose=True):
    missing = []
    for k in KEYS:
        v = get(k, required=False)
        if v:
            if verbose:
                L.log("  OK  %-15s ... %s" % (k, "*" * min(8, len(v))))
        else:
            missing.append(k)
            if verbose:
                L.warn("  --  %-15s 없음" % k)
    return missing


def mask(text, *tokens):
    out = text or ""
    for t in tokens:
        if t:
            out = out.replace(t, "****")
    return out
