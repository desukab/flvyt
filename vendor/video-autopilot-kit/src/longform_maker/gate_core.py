# -*- coding: utf-8 -*-
"""gate_core.py — shared mechanical gate shell.

Copied from Hao0321/video-autopilot-kit under its MIT license.
"""
from __future__ import annotations

def report(fails=None, warns=None, **extra) -> dict:
    fails = list(fails or [])
    warns = list(warns or [])
    rep = {"ok": not fails, "fails": fails, "warns": warns}
    rep.update(extra)
    return rep

def raise_if_failed(rep: dict, label: str, title: str) -> None:
    fails = rep.get("fails") or []
    if fails:
        raise AssertionError("[%s] %s:\n  - %s" % (label, title, "\n  - ".join(fails)))

def make_assert(gate_fn, label_fn, title: str, print_warns: bool = False, post=None):
    def _assert(spec):
        _ok, rep = gate_fn(spec)
        raise_if_failed(rep, label_fn(spec), title)
        if print_warns:
            for w in rep.get("warns") or []:
                print("   WARN " + w)
        return post(spec, rep) if post else spec
    return _assert

def selftest_runner(cases, width: int = 50, list_fails: bool = False) -> int:
    failed = []
    def check(name, cond):
        print("[%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            failed.append(name)
    if callable(cases):
        cases(check)
    else:
        for name, cond in cases:
            check(name, cond)
    print("-" * width)
    if failed:
        print("SELFTEST RED: %d failed" % len(failed))
        if list_fails:
            for f in failed:
                print("  - " + f)
        return 1
    print("SELFTEST GREEN: all checks passed")
    return 0

if __name__ == "__main__":
    def body(check):
        r = report(["a"], ["w"], dur=1.0)
        check("report marks not ok", r["ok"] is False and r["dur"] == 1.0)
        check("report ok when clean", report([], [])["ok"] is True)
        try:
            raise_if_failed({"fails": ["boom"]}, "t1", "Demo gate FAIL")
            check("raises", False)
        except AssertionError as e:
            check("raises", "[t1] Demo gate FAIL" in str(e))
    raise SystemExit(selftest_runner(body, width=54))
