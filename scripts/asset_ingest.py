#!/usr/bin/env python3
"""Ingest a user-owned/licensed asset and register its provenance."""
from __future__ import annotations
import argparse, hashlib, json, mimetypes, shutil
from pathlib import Path

ALLOWED={"owned","public-domain","cc0","cc-by","cc-by-sa","licensed"}

def main()->int:
    p=argparse.ArgumentParser(description="Copy a license-cleared asset into public/assets and register provenance")
    p.add_argument("source"); p.add_argument("--id",required=True); p.add_argument("--license",required=True,choices=sorted(ALLOWED))
    p.add_argument("--tags",default=""); p.add_argument("--attribution",default=""); p.add_argument("--source-url",default="")
    a=p.parse_args(); src=Path(a.source); root=Path(__file__).resolve().parents[1]
    if not src.is_file(): raise SystemExit(f"Asset not found: {src}")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in a.id): raise SystemExit("Asset id must contain only letters, numbers, '_' or '-'.")
    outdir=root/"public/assets"; outdir.mkdir(parents=True,exist_ok=True)
    dst=outdir/f"{a.id}{src.suffix.lower()}"; shutil.copy2(src,dst)
    digest=hashlib.sha256(dst.read_bytes()).hexdigest(); mime=mimetypes.guess_type(dst.name)[0] or "application/octet-stream"
    registry_path=root/"assets/registry.json"
    data=json.loads(registry_path.read_text()) if registry_path.exists() else {"assets":[]}
    data.setdefault("assets",[]); data["assets"]=[x for x in data["assets"] if x.get("id")!=a.id]
    data["assets"].append({"id":a.id,"path":f"public/assets/{dst.name}","kind":"image" if mime.startswith("image/") else "video","tags":[x for x in a.tags.split(",") if x],"license":a.license,"attribution":a.attribution,"source":a.source_url,"sha256":digest,"mime":mime,"duration":0})
    registry_path.parent.mkdir(parents=True,exist_ok=True); registry_path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    print(f"Registered {dst} ({digest[:12]}…)")
    return 0
if __name__=="__main__": raise SystemExit(main())
