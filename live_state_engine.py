#!/usr/bin/env python3
"""Replay sourced live-game observations. This validates extracted data, NOT screenshot pixels."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Any

KINDS={"SCREEN","MATCH_SCHEDULE","MATCH_ATTEMPT","MATCHES_COMPLETED","TRAINING",
       "ITEM_USE","CORRECTION","SAVE_CHECKPOINT","ROLLBACK"}
SOURCES={"RAW_SCREEN","USER_REPORT","USER_CORRECTION"}
BRANCHES={"ACCEPTED","REJECTED"}
COUNTERS=("study","sports","play","nature","cheer")

class ObservationError(ValueError):
    pass

def period(e):
    p=e.get("period")
    if not isinstance(p,dict) or type(p.get("year")) is not int or type(p.get("month")) is not int:
        raise ObservationError("period needs integer year and month")
    if p["year"]<1 or not 1<=p["month"]<=12:raise ObservationError("invalid period")
    return p["year"],p["month"]

def label(p):
    return f"Y{p[0]}-{p[1]:02d}"

def clock_minutes(s):
    if not isinstance(s,str):return None
    m=re.fullmatch(r"(AM|PM)\s*(1[0-2]|[1-9]):([0-5][0-9])",s.strip(),re.I)
    if not m:return None
    return (int(m.group(2))%12)*60+int(m.group(3))+(720 if m.group(1).upper()=="PM" else 0)

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
        if e["kind"]!="CORRECTION":
            base[e["event_id"]]=dict(e)
            continue
        target=e.get("target_event_id");patch=e.get("patch")
        if target not in base or not isinstance(patch,dict) or not patch:
            raise ObservationError("correction needs earlier target and nonempty patch")
        if not set(patch).issubset({"opponent","our_runs","their_runs","player","skill"}):
            raise ObservationError("correction cannot rewrite time, branch, source or event identity")
        for key,value in patch.items():
            if key in {"our_runs","their_runs"} and (type(value) is not int or value<0):
                raise ObservationError("corrected runs must be nonnegative integer")
            if key in {"opponent","player","skill"} and (not isinstance(value,str) or not value):
                raise ObservationError("corrected text must be nonempty")
        base[target].update(patch)
    return [base[e["event_id"]] for e in events if e["kind"]!="CORRECTION"]

def resolve_active_lineage(events):
    """Keep discarded branches for audit, but never apply their skills/items to current state."""
    active=[];discarded=[];discarded_match_ids=set();rollback_count=0
    for e in events:
        if e["kind"]!="ROLLBACK":
            active.append(e)
            continue
        cp=e.get("to_checkpoint_id")
        if not isinstance(cp,str) or not cp:
            raise ObservationError(f"{e['event_id']}: rollback requires to_checkpoint_id")
        index=next((i for i,v in enumerate(active) if v["event_id"]==cp and v["kind"]=="SAVE_CHECKPOINT"),None)
        if index is None:
            raise ObservationError(f"{e['event_id']}: rollback checkpoint is not active")
        removed=active[index+1:]
        discarded.extend(x["event_id"] for x in removed if x["kind"]!="ROLLBACK")
        discarded_match_ids.update(x.get("match_id") for x in removed if x["kind"]=="MATCH_ATTEMPT")
        active=active[:index+1]+[e]
        rollback_count+=1
    return active,discarded,discarded_match_ids,rollback_count

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
    if seqs!=list(range(1,len(events)+1)):
        raise ObservationError("event seq must be contiguous starting at 1")
    corrected=apply_corrections(events)
    active,discarded,reverted_match_ids,rollback_count=resolve_active_lineage(corrected)
    prior_first={}
    for e in corrected:
        if e["kind"]=="MATCH_ATTEMPT" and e.get("attempt")==1 and e.get("match_id") not in prior_first:
            prior_first[e["match_id"]]={"attempt":1,"our_runs":e.get("our_runs"),
                "their_runs":e.get("their_runs"),"evidence_id":e["event_id"]}
    state={"schema_version":"1.1","last_event_seq":len(events),"period_floor":None,
           "last_seen_screen_period":None,
           "resources":{"fresh":False,"values":None,"last_observed":None},
           "matches":{},"completed_match_periods":[],"skills":[],
           "training_counts_by_player_drill":{},"item_effects":[],
           "observations_ignored_as_stale":[],"reverted_event_ids":discarded,
           "rollback_count":rollback_count,"current_exact_time":"UNKNOWN"}
    floor=None;closed=set();matches={};seen_attempts=set()
    last_mutation_id=None;last_screen_clock=None;last_screen_period=None
    def invalidate():
        state["resources"]["fresh"]=False
        state["resources"]["values"]=None
    for e in active:
        kind=e["kind"];p=period(e);pk=label(p);eid=e["event_id"]
        historical=bool(floor and p<floor)
        if kind=="SCREEN":
            vals=e.get("resources")
            if not isinstance(vals,dict) or not set(COUNTERS).issubset(vals):
                raise ObservationError(f"{eid}: SCREEN missing required resource counters")
            if any(type(vals[x]) is not int or vals[x]<0 for x in COUNTERS):
                raise ObservationError(f"{eid}: invalid resource counter")
            if "money_yen" in e and (type(e["money_yen"]) is not int or e["money_yen"]<0):
                raise ObservationError(f"{eid}: invalid money")
            after=e.get("observed_after_event_id")
            mutation_unresolved=last_mutation_id is not None
            if (historical or e.get("branch")!="ACCEPTED" or
                (mutation_unresolved and after!=last_mutation_id) or
                (pk in closed and e.get("confirmed_after_period_completion") is not True)):
                state["observations_ignored_as_stale"].append(eid)
                continue
            current_clock=clock_minutes(e.get("clock"))
            if last_screen_period==pk and last_screen_clock is not None and current_clock is not None and current_clock<last_screen_clock and not e.get("confirmed_clock_reset"):
                state["observations_ignored_as_stale"].append(eid)
                continue
            state["last_seen_screen_period"]=pk
            state["resources"]={"fresh":True,"values":{k:vals[k] for k in COUNTERS},"last_observed":eid}
            state["current_exact_time"]=e.get("clock") or "UNKNOWN"
            floor=max(floor,p) if floor else p
            last_screen_clock=current_clock;last_screen_period=pk;last_mutation_id=None
        elif kind=="MATCH_SCHEDULE":
            if not isinstance(e.get("entries"),list):raise ObservationError(f"{eid}: entries required")
            for item in e["entries"]:
                if not isinstance(item,dict):raise ObservationError(f"{eid}: invalid schedule entry")
                mid=item.get("match_id");opp=item.get("opponent")
                if not isinstance(mid,str) or not mid or not isinstance(opp,str) or not opp or mid in matches:
                    raise ObservationError(f"{eid}: duplicate/invalid schedule entry")
                matches[mid]={"opponent":opp,"period":pk,
                    "status":"COMPLETED_SCORE_UNKNOWN" if pk in closed else "SCHEDULED",
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
            if (mid,n) in seen_attempts:raise ObservationError(f"{eid}: duplicate active match attempt")
            seen_attempts.add((mid,n))
            result={"attempt":n,"our_runs":a,"their_runs":b,"evidence_id":eid}
            if n==1:m["first_attempt"]=result
            if e["branch"]=="ACCEPTED":
                if m["accepted_attempt"] is not None:raise ObservationError(f"{eid}: multiple accepted branches")
                m["accepted_attempt"]=result;m["status"]="PLAYED"
                reset_assisted=(n>1 or mid in reverted_match_ids)
                m["classification"]=(("RESET_ASSISTED_WIN" if reset_assisted else "STABLE_WIN")
                    if a>b else ("DRAW" if a==b else "LOSS"))
                if not historical:
                    invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid
                    floor=max(floor,p) if floor else p
        elif kind=="MATCHES_COMPLETED":
            if e["source"]["kind"] not in {"USER_REPORT","USER_CORRECTION"}:
                raise ObservationError(f"{eid}: period completion requires user assertion")
            closed.add(pk)
            for m in matches.values():
                if m["period"]==pk and m["status"]=="SCHEDULED":m["status"]="COMPLETED_SCORE_UNKNOWN"
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid
                floor=max(floor,p) if floor else p
        elif kind=="TRAINING":
            if e.get("branch")!="ACCEPTED":continue
            players=e.get("participants");drill=e.get("drill")
            if not isinstance(players,list) or len(players)!=3 or len(set(players))!=3 or not all(isinstance(x,str) and x for x in players) or not isinstance(drill,str) or not drill:
                raise ObservationError(f"{eid}: training requires three distinct participants and drill")
            awards=e.get("skill_awards",[])
            if not isinstance(awards,list):raise ObservationError(f"{eid}: skill_awards must be list")
            for award in awards:
                if not isinstance(award,dict) or award.get("player") not in players or not isinstance(award.get("skill"),str) or not award["skill"]:
                    raise ObservationError(f"{eid}: invalid skill award")
                state["skills"].append({"player":award["player"],"skill":award["skill"],"evidence_id":eid})
            for player in players:
                k=f"{player}|{drill}"
                state["training_counts_by_player_drill"][k]=state["training_counts_by_player_drill"].get(k,0)+1
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid
                floor=max(floor,p) if floor else p
        elif kind=="ITEM_USE":
            if e.get("branch")!="ACCEPTED":continue
            bundle=e.get("item_bundle")
            if not isinstance(bundle,list) or not bundle or any(
                not isinstance(x,dict) or not isinstance(x.get("item"),str) or not x["item"] or
                type(x.get("quantity")) is not int or x["quantity"]<1 for x in bundle):
                raise ObservationError(f"{eid}: item use needs item_bundle with positive quantity")
            delta=e.get("effect_deltas",{})
            if not isinstance(delta,dict) or any(not isinstance(k,str) or type(v) is not int for k,v in delta.items()):
                raise ObservationError(f"{eid}: invalid effect_deltas")
            state["item_effects"].append({"event_id":eid,"item_bundle":bundle,"effect_deltas":delta})
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid
                floor=max(floor,p) if floor else p
        elif kind=="ROLLBACK":
            invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid
            last_screen_clock=None;last_screen_period=None
        elif kind=="SAVE_CHECKPOINT":
            pass
    for mid,m in matches.items():
        if m["first_attempt"] is None and mid in prior_first:
            m["first_attempt"]=prior_first[mid]
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
    if action_type=="MATCH":
        if not rec.get("target_match_id"):errors.append("MATCH_ID_REQUIRED")
        if not rec.get("target_period"):errors.append("MATCH_PERIOD_REQUIRED")
        if rec.get("target_period") in state["completed_match_periods"]:
            errors.append("COMPLETED_PERIOD_MATCH")
    if action_type=="TRAIN":
        players=rec.get("participants")
        if rec.get("cheer") not in {"ON","OFF"} or not isinstance(players,list) or len(players)!=3 or not all(isinstance(x,str) and x for x in players) or len(set(players))!=3:
            errors.append("TRAINING_DETAILS_REQUIRED")
        if not isinstance(rec.get("spend"),dict) or "sports" not in rec["spend"]:
            errors.append("TRAINING_COST_REQUIRED")
        if rec.get("cheer")=="ON" and (not isinstance(rec.get("spend"),dict) or "cheer" not in rec["spend"]):
            errors.append("CHEER_COST_REQUIRED")
        if not state["resources"]["fresh"]:errors.append("STALE_RESOURCES")
    if action_type in {"ITEM","ACTIVITY"} and not isinstance(rec.get("spend"),dict):
        errors.append("COST_DECLARATION_REQUIRED")
    mid=rec.get("target_match_id")
    if mid:
        m=state["matches"].get(mid)
        if m is None:errors.append("UNKNOWN_MATCH")
        elif m["status"]!="SCHEDULED" or m["period"] in state["completed_match_periods"]:
            errors.append("ALREADY_COMPLETED_MATCH")
        elif action_type=="MATCH" and m["period"]!=rec.get("target_period"):
            errors.append("MATCH_PERIOD_MISMATCH")
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
              "resources_fresh":state["resources"]["fresh"],"completed_months":state["completed_match_periods"],
              "rollbacks":state["rollback_count"]},ensure_ascii=False))
        return 0
    except (ObservationError,OSError,ValueError) as exc:
        print(json.dumps({"result":"FAIL","error":str(exc)},ensure_ascii=False));return 1

if __name__=="__main__":raise SystemExit(main())
