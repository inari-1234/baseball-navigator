#!/usr/bin/env python3
"""Deterministic replay of source-linked observations, not image OCR."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

KINDS={"SCREEN","MATCH_SCHEDULE","MATCH_ATTEMPT","MATCHES_COMPLETED","TRAINING","ITEM_USE","CORRECTION","ROLLBACK"}
SOURCES={"RAW_SCREEN","USER_REPORT","USER_CORRECTION"}
BRANCHES={"ACCEPTED","REJECTED"}

class ObservationError(ValueError): pass

def period(e):
    p=e.get("period")
    if not isinstance(p,dict) or type(p.get("year")) is not int or type(p.get("month")) is not int:
        raise ObservationError("period needs integer year and month")
    if p["year"]<1 or not 1<=p["month"]<=12:raise ObservationError("invalid period")
    return p["year"],p["month"]

def label(p):return f"Y{p[0]}-{p[1]:02d}"

def read_events(path):
    out=[]
    for line_no,line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():continue
        try:e=json.loads(line)
        except json.JSONDecodeError as exc:raise ObservationError(f"line {line_no}: {exc}") from exc
        if not isinstance(e,dict):raise ObservationError(f"line {line_no}: not an object")
        out.append(e)
    return out

def apply_corrections(events):
    base={}
    for e in events:
        if e["kind"]!="CORRECTION":base[e["event_id"]]=dict(e);continue
        target=e.get("target_event_id");patch=e.get("patch")
        if target not in base or not isinstance(patch,dict) or not patch:
            raise ObservationError("correction needs earlier target and nonempty patch")
        if not set(patch).issubset({"opponent","our_runs","their_runs","player","skill"}):
            raise ObservationError("correction cannot rewrite time, branch, source or event identity")
        base[target].update(patch)
    return [base[e["event_id"]] for e in events if e["kind"]!="CORRECTION"]

def replay(events):
    ids=set();seqs=[]
    for e in events:
        if not isinstance(e,dict) or e.get("kind") not in KINDS:raise ObservationError("invalid kind")
        eid=e.get("event_id")
        if not isinstance(eid,str) or not eid or eid in ids:raise ObservationError("duplicate/missing event_id")
        ids.add(eid);seqs.append(e.get("seq"))
        source=e.get("source")
        if not isinstance(source,dict) or source.get("kind") not in SOURCES or not isinstance(source.get("locator"),str) or not source["locator"].strip():
            raise ObservationError(f"{eid}: missing source kind/locator")
        if e["kind"]!="CORRECTION":period(e)
    if seqs!=list(range(1,len(events)+1)):raise ObservationError("event seq must be contiguous starting at 1")
    state={"schema_version":"1.0","last_event_seq":len(events),"period_floor":None,"last_seen_screen_period":None,
           "resources":{"fresh":False,"values":None,"last_observed":None},
           "matches":{},"completed_match_periods":[],"skills":[],
           "observations_ignored_as_stale":[],"current_exact_time":"UNKNOWN"}
    floor=None;closed=set();matches={};seen_attempts=set()
    def invalidate():
        state["resources"]["fresh"]=False
        state["resources"]["values"]=None
    for e in apply_corrections(events):
        kind=e["kind"];p=period(e);pk=label(p);eid=e["event_id"]
        historical=bool(floor and p<floor)
        if kind=="SCREEN":
            vals=e.get("resources")
            if not isinstance(vals,dict) or not {"study","sports","play","nature","cheer"}.issubset(vals):
                raise ObservationError(f"{eid}: SCREEN missing required resource counters")
            if any(type(vals[x]) is not int or vals[x]<0 for x in ("study","sports","play","nature","cheer")):
                raise ObservationError(f"{eid}: invalid resource counter")
            if "money_yen" in e and (type(e["money_yen"]) is not int or e["money_yen"]<0):
                raise ObservationError(f"{eid}: invalid money")
            if historical or e.get("branch")!="ACCEPTED" or (pk in closed and e.get("confirmed_after_period_completion") is not True):
                state["observations_ignored_as_stale"].append(eid);continue
            state["last_seen_screen_period"]=pk
            state["resources"]={"fresh":True,"values":dict(vals),"last_observed":eid}
            state["current_exact_time"]=e.get("clock") or "UNKNOWN"
            floor=max(floor,p) if floor else p
        elif kind=="MATCH_SCHEDULE":
            if not isinstance(e.get("entries"),list):raise ObservationError(f"{eid}: entries required")
            for item in e["entries"]:
                mid=item.get("match_id");opp=item.get("opponent")
                if not mid or not opp or mid in matches:raise ObservationError(f"{eid}: duplicate/invalid schedule entry")
                matches[mid]={"opponent":opp,"period":pk,"status":"COMPLETED_SCORE_UNKNOWN" if pk in closed else "SCHEDULED",
                              "first_attempt":None,"accepted_attempt":None,"classification":None}
        elif kind=="MATCH_ATTEMPT":
            mid=e.get("match_id");n=e.get("attempt");a=e.get("our_runs");b=e.get("their_runs")
            if not isinstance(mid,str) or not mid or type(n) is not int or n<1 or any(type(v) is not int or v<0 for v in (a,b)):
                raise ObservationError(f"{eid}: invalid match/attempt/score")
            if e.get("branch") not in BRANCHES:raise ObservationError(f"{eid}: branch required")
            if mid not in matches:
                if not e.get("opponent"):raise ObservationError(f"{eid}: unscheduled match needs opponent")
                matches[mid]={"opponent":e["opponent"],"period":pk,"status":"UNRESOLVED",
                              "first_attempt":None,"accepted_attempt":None,"classification":None}
            m=matches[mid]
            if m["period"]!=pk:raise ObservationError(f"{eid}: match period conflict")
            if e.get("opponent") and e["opponent"]!=m["opponent"]:
                raise ObservationError(f"{eid}: opponent conflict: submit CORRECTION")
            if (mid,n) in seen_attempts:raise ObservationError(f"{eid}: duplicate match attempt")
            seen_attempts.add((mid,n))
            result={"attempt":n,"our_runs":a,"their_runs":b,"evidence_id":eid}
            if n==1:m["first_attempt"]=result
            if e["branch"]=="ACCEPTED":
                if m["accepted_attempt"] is not None:raise ObservationError(f"{eid}: multiple accepted branches")
                m["accepted_attempt"]=result;m["status"]="PLAYED"
                m["classification"]=("STABLE_WIN" if n==1 else "RESET_ASSISTED_WIN") if a>b else ("DRAW" if a==b else "LOSS")
                if not historical:invalidate();state["current_exact_time"]="UNKNOWN"
                floor=max(floor,p) if floor else p
        elif kind=="MATCHES_COMPLETED":
            if e["source"]["kind"] not in {"USER_REPORT","USER_CORRECTION"}:
                raise ObservationError(f"{eid}: period completion requires user assertion")
            closed.add(pk)
            for m in matches.values():
                if m["period"]==pk and m["status"]=="SCHEDULED":m["status"]="COMPLETED_SCORE_UNKNOWN"
            if not historical:invalidate();state["current_exact_time"]="UNKNOWN"
            floor=max(floor,p) if floor else p
        elif kind=="TRAINING":
            if e.get("branch")!="ACCEPTED":continue
            if not e.get("player") or not e.get("drill"):raise ObservationError(f"{eid}: training needs player/drill")
            if e.get("skill"):state["skills"].append({"player":e["player"],"skill":e["skill"],"evidence_id":eid})
            if not historical:invalidate()
        elif kind in {"ITEM_USE","ROLLBACK"}:
            if not historical and (kind=="ROLLBACK" or e.get("branch")=="ACCEPTED"):invalidate()
            if not historical:state["current_exact_time"]="UNKNOWN"
    state["period_floor"]=label(floor) if floor else None
    state["completed_match_periods"]=sorted(closed)
    state["matches"]=dict(sorted(matches.items()))
    return state

def validate_recommendation(rec,state,contract):
    errors=[]
    if rec.get("based_on_event_seq")!=state["last_event_seq"]:
        errors.append("STALE_REVISION")
    active={r["rule_id"] for r in contract.get("rules",[]) if r.get("status")=="ACTIVE"}
    ids=rec.get("rule_ids")
    if not isinstance(ids,list) or not ids or any(r not in active for r in ids):
        errors.append("INVALID_RULE_ID")
    action_type=rec.get("action_type")
    if action_type not in {"MATCH","TRAIN","ITEM","ACTIVITY","OTHER"}:
        errors.append("ACTION_TYPE_REQUIRED")
    if action_type=="MATCH" and not rec.get("target_match_id"):
        errors.append("MATCH_ID_REQUIRED")
    if action_type=="MATCH" and rec.get("target_period") in state["completed_match_periods"]:
        errors.append("COMPLETED_PERIOD_MATCH")
    if action_type=="TRAIN":
        if rec.get("cheer") not in {"ON","OFF"} or not isinstance(rec.get("participants"),list) or len(rec["participants"])!=3 or len(set(rec["participants"]))!=3:
            errors.append("TRAINING_DETAILS_REQUIRED")
        if not isinstance(rec.get("spend"),dict) or "sports" not in rec["spend"]:
            errors.append("TRAINING_COST_REQUIRED")
        if not state["resources"]["fresh"]:
            errors.append("STALE_RESOURCES")
    mid=rec.get("target_match_id")
    if mid:
        m=state["matches"].get(mid)
        if m is None:errors.append("UNKNOWN_MATCH")
        elif m["status"]!="SCHEDULED" or m["period"] in state["completed_match_periods"]:
            errors.append("ALREADY_COMPLETED_MATCH")
    spend=rec.get("spend",{})
    if not isinstance(spend,dict):errors.append("INVALID_SPEND")
    elif spend:
        if not state["resources"]["fresh"]:errors.append("STALE_RESOURCES")
        else:
            vals=state["resources"]["values"]
            for key,value in spend.items():
                if key not in vals or type(value) is not int or value<0 or value>vals[key]:
                    errors.append(f"INSUFFICIENT_OR_UNKNOWN_RESOURCE:{key}")
    return errors

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--events",default="LIVE_EVENTS.jsonl")
    ap.add_argument("--snapshot",default="CURRENT_LIVE_STATE.json")
    ap.add_argument("--contract",default="DECISION_CONTRACT.json")
    args=ap.parse_args()
    try:
        state=replay(read_events(args.events))
        saved=json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        contract=json.loads(Path(args.contract).read_text(encoding="utf-8"))
        if state!=saved:raise ObservationError("CURRENT_LIVE_STATE.json differs from event replay")
        if not isinstance(contract.get("rules"),list):raise ObservationError("invalid contract rules")
        print(json.dumps({"result":"PASS","events":state["last_event_seq"],"period_floor":state["period_floor"],
              "resources_fresh":state["resources"]["fresh"],"completed_months":state["completed_match_periods"]},ensure_ascii=False))
        return 0
    except (ObservationError,OSError,ValueError) as exc:
        print(json.dumps({"result":"FAIL","error":str(exc)},ensure_ascii=False));return 1

if __name__=="__main__":raise SystemExit(main())
