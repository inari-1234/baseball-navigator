#!/usr/bin/env python3
"""Deterministic replay of source-linked observations, not image OCR."""
from __future__ import annotations
import argparse
import copy
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
        if e["kind"]!="CORRECTION":base[e["event_id"]]=copy.deepcopy(e);continue
        target=e.get("target_event_id");match_id=e.get("target_match_id");patch=e.get("patch")
        if not isinstance(patch,dict) or not patch or (bool(target)==bool(match_id)):
            raise ObservationError("correction requires exactly one earlier event or match target and a patch")
        if match_id:
            if set(patch)!={"opponent"} or not isinstance(patch["opponent"],str) or not patch["opponent"]:
                raise ObservationError("match-level correction supports only a verified opponent name")
            found=False
            for old in base.values():
                if old["kind"]=="MATCH_ATTEMPT" and old.get("match_id")==match_id:
                    old["opponent"]=patch["opponent"];found=True
                if old["kind"]=="MATCH_SCHEDULE":
                    for row in old.get("entries",[]):
                        if row.get("match_id")==match_id:
                            row["opponent"]=patch["opponent"];found=True
            if not found:raise ObservationError("match-level correction target not found")
        else:
            if target not in base:raise ObservationError("correction target event not found")
            if not set(patch).issubset({"opponent","our_runs","their_runs","player","skill"}):
                raise ObservationError("correction cannot rewrite time, branch, source or event identity")
            base[target].update(patch)
    return [base[e["event_id"]] for e in events if e["kind"]!="CORRECTION"]

def select_active_timeline(events):
    """Preserve event audit, but exclude operations undone by restoring an earlier save."""
    active=[];discarded=[];unanchored=None
    for event in events:
        if event["kind"]!="ROLLBACK":
            active.append(event)
            continue
        restore=event.get("restore_to_event_id")
        if restore is None:
            discarded.extend(x["event_id"] for x in active if x["kind"]!="ROLLBACK")
            active=[]
            unanchored=event["event_id"]
        else:
            positions=[i for i,x in enumerate(active) if x["event_id"]==restore]
            if len(positions)!=1:
                raise ObservationError(f'{event["event_id"]}: rollback restore point is missing or discarded')
            i=positions[0]
            discarded.extend(x["event_id"] for x in active[i+1:] if x["kind"]!="ROLLBACK")
            active=active[:i+1]
            if unanchored and not any(x["event_id"]==unanchored for x in active):
                unanchored=None
        active.append(event)
    return active,discarded,unanchored


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
    active_events,discarded,unanchored=select_active_timeline(events)
    state={"schema_version":"1.1","last_event_seq":len(events),"period_floor":None,"last_seen_screen_period":None,
           "resources":{"fresh":False,"values":None,"last_observed":None},
           "matches":{},"completed_match_periods":[],"skills":[],"item_uses":[],
           "training_counts_observed":{},"training_history":[],
           "discarded_branch_event_ids":discarded,"timeline_status":"UNKNOWN_AFTER_ROLLBACK" if unanchored else "TRUSTED",
           "observations_ignored_as_stale":[],"current_exact_time":"UNKNOWN"}
    floor=None;closed=set();matches={};seen_attempts=set();resource_anchor=None
    def invalidate(event_id):
        nonlocal resource_anchor
        resource_anchor=event_id
        state["resources"]["fresh"]=False
        state["resources"]["values"]=None
    for e in apply_corrections(active_events):
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
            if historical or e.get("branch")!="ACCEPTED" or (resource_anchor is not None and e.get("after_event_id")!=resource_anchor):
                state["observations_ignored_as_stale"].append(eid);continue
            state["last_seen_screen_period"]=pk
            state["resources"]={"fresh":True,"values":dict(vals),"last_observed":eid}
            state["current_exact_time"]=e.get("clock") or "UNKNOWN"
            if unanchored and e.get("after_event_id")==unanchored:
                state["timeline_status"]="RECAPTURED_AFTER_UNANCHORED_ROLLBACK"
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
                if not historical:invalidate(eid);state["current_exact_time"]="UNKNOWN"
                floor=max(floor,p) if floor else p
        elif kind=="MATCHES_COMPLETED":
            if e["source"]["kind"] not in {"USER_REPORT","USER_CORRECTION"}:
                raise ObservationError(f"{eid}: period completion requires user assertion")
            closed.add(pk)
            for m in matches.values():
                if m["period"]==pk and m["status"]=="SCHEDULED":m["status"]="COMPLETED_SCORE_UNKNOWN"
            if not historical:invalidate(eid);state["current_exact_time"]="UNKNOWN"
            floor=max(floor,p) if floor else p
        elif kind=="TRAINING":
            participants=e.get("participants")
            drill=e.get("drill");level=e.get("drill_level");cheer=e.get("cheer");awards=e.get("skill_awards",[])
            if (e.get("branch") not in BRANCHES or not isinstance(participants,list) or len(participants)!=3
                or any(not isinstance(x,str) or not x for x in participants) or len(set(participants))!=3
                or not isinstance(drill,str) or not drill or type(level) is not int or level<1
                or cheer not in {"ON","OFF"} or not isinstance(awards,list)):
                raise ObservationError(f"{eid}: training requires exact three participants, drill, level, cheer and branch")
            if any(not isinstance(x,dict) or x.get("player") not in participants or not isinstance(x.get("skill"),str) or not x["skill"] for x in awards):
                raise ObservationError(f"{eid}: invalid skill recipient or skill")
            if e["branch"]=="ACCEPTED":
                state["training_history"].append({"evidence_id":eid,"participants":list(participants),
                        "drill":drill,"drill_level":level,"cheer":cheer})
                for player in participants:
                    counter=state["training_counts_observed"].setdefault(player,{})
                    counter[drill]=counter.get(drill,0)+1
                for award in awards:
                    state["skills"].append({"player":award["player"],"skill":award["skill"],"evidence_id":eid})
                if not historical:invalidate(eid)
        elif kind=="ITEM_USE":
            if e.get("branch") not in BRANCHES:raise ObservationError(f"{eid}: item use needs ACCEPTED or REJECTED branch")
            if e["branch"]=="ACCEPTED":
                state["item_uses"].append({"evidence_id":eid,"items":e.get("items"),"observed_delta":e.get("observed_delta")})
                if not historical:invalidate(eid)
        elif kind=="ROLLBACK":
            if not historical:invalidate(eid);state["current_exact_time"]="UNKNOWN"
    state["period_floor"]=label(floor) if floor else None
    state["completed_match_periods"]=sorted(closed)
    state["matches"]=dict(sorted(matches.items()))
    return state

def validate_recommendation(rec,state,contract):
    errors=[]
    if rec.get("based_on_event_seq")!=state["last_event_seq"]:
        errors.append("STALE_REVISION")
    if state.get("timeline_status")=="UNKNOWN_AFTER_ROLLBACK":
        errors.append("UNRESOLVED_ROLLBACK")
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
    if action_type=="MATCH" and rec.get("target_period") and state["period_floor"] and rec["target_period"]<state["period_floor"]:
        errors.append("PAST_PERIOD_MATCH")
    if action_type=="TRAIN":
        if rec.get("cheer") not in {"ON","OFF"} or not isinstance(rec.get("participants"),list) or len(rec["participants"])!=3 or len(set(rec["participants"]))!=3:
            errors.append("TRAINING_DETAILS_REQUIRED")
        if not isinstance(rec.get("spend"),dict) or "sports" not in rec["spend"] or type(rec["spend"]["sports"]) is not int or rec["spend"]["sports"]<=0:
            errors.append("TRAINING_COST_REQUIRED")
        if rec.get("cheer")=="ON" and (not isinstance(rec.get("spend"),dict) or type(rec["spend"].get("cheer")) is not int or rec["spend"]["cheer"]<=0):
            errors.append("CHEER_COST_REQUIRED")
        if not state["resources"]["fresh"]:
            errors.append("STALE_RESOURCES")
    mid=rec.get("target_match_id")
    if mid:
        m=state["matches"].get(mid)
        if m is None:errors.append("UNKNOWN_MATCH")
        elif m["status"]!="SCHEDULED" or m["period"] in state["completed_match_periods"]:
            errors.append("ALREADY_COMPLETED_MATCH")
        elif state["period_floor"] and m["period"]<state["period_floor"]:
            errors.append("PAST_PERIOD_MATCH")
        if m is not None and rec.get("target_period") and rec["target_period"]!=m["period"]:
            errors.append("MATCH_PERIOD_CONFLICT")
    if action_type=="ITEM":
        errors.append("ITEM_INVENTORY_NOT_VERIFIED")  # no canonical item-count snapshot yet; fail closed
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
