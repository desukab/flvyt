"""Human-editor-inspired pacing rules shared by planning and rendering."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class EditDecision:
 mode:str
 max_text_chars:int
 min_seconds:float
 max_seconds:float

POLICY={
 "hook":EditDecision("punch",72,1.2,4.5),
 "claim":EditDecision("establish",105,1.4,6.0),
 "evidence":EditDecision("detail",115,1.6,7.0),
 "context":EditDecision("establish",115,1.8,7.0),
 "implication":EditDecision("punch",105,1.4,6.0),
 "thesis":EditDecision("hold",125,2.0,8.0),
 "close":EditDecision("hold",105,2.0,6.0),
}

def decision(kind:str,emphasis:str="normal")->EditDecision:
 d=POLICY.get(kind,POLICY["claim"])
 if emphasis=="high": return EditDecision("punch",d.max_text_chars,max(1.2,d.min_seconds-.2),d.max_seconds)
 return d

def clamp_text(text:str,kind:str)->str:
 d=decision(kind)
 text=" ".join(text.split())
 if len(text)<=d.max_text_chars:return text
 cut=text[:d.max_text_chars].rsplit(" ",1)[0]
 return cut.rstrip(" ,;:")+"…"
