"""Deterministic, provenance-aware asset registry."""
from __future__ import annotations
import hashlib,json,mimetypes
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable
ALLOWED_LICENSES={"owned","public-domain","cc0","cc-by","cc-by-sa","licensed"}
@dataclass(frozen=True)
class Asset:
 id:str; path:str; kind:str; tags:tuple[str,...]=(); license:str="owned"; attribution:str=""; source:str=""; duration:float=0.0; sha256:str=""; mime:str=""
 def valid(self)->bool:return self.license.lower() in ALLOWED_LICENSES and bool(self.path)
class AssetRegistry:
 def __init__(self,assets:Iterable[Asset]=()):self.assets=list(assets)
 @classmethod
 def load(cls,path:str|Path)->"AssetRegistry":
  data=json.loads(Path(path).read_text(encoding="utf-8")); assets=[]
  for r in data.get("assets",[]): assets.append(Asset(id=str(r["id"]),path=str(r["path"]),kind=str(r.get("kind","image")),tags=tuple(str(x).lower() for x in r.get("tags",[])),license=str(r.get("license","owned")),attribution=str(r.get("attribution","")),source=str(r.get("source",r.get("source_url",""))),duration=float(r.get("duration",0)),sha256=str(r.get("sha256","")),mime=str(r.get("mime",""))))
  return cls(assets)
 def validate(self,root:str|Path|None=None)->list[str]:
  root=Path(root or "."); errors=[]; seen=set()
  for a in self.assets:
   if a.id in seen: errors.append(f"{a.id}: duplicate id")
   seen.add(a.id)
   if not a.valid(): errors.append(f"{a.id}: unsupported/missing license"); continue
   p=Path(a.path); p=p if p.is_absolute() else root/p
   if not p.is_file(): errors.append(f"{a.id}: missing file {p}"); continue
   actual=hashlib.sha256(p.read_bytes()).hexdigest()
   if a.sha256 and actual.lower()!=a.sha256.lower(): errors.append(f"{a.id}: sha256 mismatch")
   if a.mime and mimetypes.guess_type(p.name)[0] and a.mime!=mimetypes.guess_type(p.name)[0]: errors.append(f"{a.id}: MIME mismatch")
  return errors
 def match(self,query:str,kind:str|None=None)->list[Asset]:
  tokens={t.lower() for t in query.replace(","," ").split() if t}; scored=[]
  for a in self.assets:
   if not a.valid() or (kind and a.kind!=kind):continue
   score=len(tokens&set(a.tags))+(1 if a.kind==kind else 0)
   if score:scored.append((score,a))
  scored.sort(key=lambda x:(-x[0],x[1].id)); return [a for _,a in scored]
 def manifest(self)->dict:return {"assets":[asdict(a) for a in self.assets]}
