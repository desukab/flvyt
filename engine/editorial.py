"""Sentence-level editorial grammar for automated documentary pacing."""
from __future__ import annotations
import re
from typing import Any
from .edit_policy import decision

def _tokens(text:str)->list[str]: return re.findall(r"\b[\w'-]+\b",text)

def make_shots(text:str,seconds:float,visual:str,emphasis:str="normal")->list[dict[str,Any]]:
 duration=max(0.8,float(seconds)); words=len(_tokens(text)); policy=decision("claim",emphasis)
 if duration<3.0 or words<8:return [{"id":"s1","seconds":round(duration,3),"visual":visual,"text":text,"mode":policy.mode}]
 if visual in {"text","claim","quote"}: modes=[(.42,visual,"establish"),(.34,visual,"punch"),(.24,visual,"hold")]
 elif visual in {"counter","stat"}: modes=[(.36,visual,"count"),(.38,visual,"detail"),(.26,visual,"hold")]
 elif visual in {"map","timeline"}: modes=[(.38,visual,"establish"),(.36,visual,"move"),(.26,visual,"hold")]
 else:modes=[(.50,visual,"establish"),(.30,visual,"punch"),(.20,visual,"hold")]
 if emphasis=="high":modes=[(.34,modes[0][1],modes[0][2]),(.36,modes[1][1],modes[1][2]),(.30,modes[2][1],modes[2][2])]
 shots=[]; used=0.0
 for i,(fraction,v,mode) in enumerate(modes):
  s=duration*fraction if i<len(modes)-1 else duration-used; s=max(.65,s) if i<len(modes)-1 else s; used+=s
  shots.append({"id":f"s{i+1}","seconds":round(s,3),"visual":v,"text":text,"mode":mode})
 shots[-1]["seconds"]=round(duration-sum(float(s["seconds"]) for s in shots[:-1]),3)
 return shots

def add_shots(beats:list[Any])->list[Any]:
 for beat in beats: beat.shots=make_shots(beat.text,beat.seconds,beat.visual,beat.emphasis)
 return beats
