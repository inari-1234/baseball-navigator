#!/usr/bin/env python3
"""Replay sourced live-game observations. This validates extracted data, NOT screenshot pixels."""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

KINDS={"SCREEN","MATCH_SCHEDULE","MATCH_ATTEMPT","MATCHES_COMPLETED","TRAINING",
       "ITEM_USE","CORRECTION","SAVE_CHECKPOINT","ROLLBACK","HP_OBSERVATION"}
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


def measure_hp_observation(entry, source_kind):
    """Keep visual bar fill distinct from actual numeric HP; no screenshot OCR is implied."""
    if not isinstance(entry,dict) or not isinstance(entry.get("player"),str) or not entry["player"].strip():
        raise ObservationError("HP needs a named player")
    kind=entry.get("reading_kind")
    if kind=="VERTICAL_BAR":
        if source_kind!="RAW_SCREEN" or entry.get("identity_evidence") not in {"SELECTED_PLAYER_PANEL","VISIBLE_ROSTER_ROW","VERIFIED_FORMATION_SLOT"}:
            raise ObservationError("bar needs a screenshot source and independently grounded player identity")
        g=entry.get("geometry_px")
        if not isinstance(g,dict):raise ObservationError("bar requires pixel geometry")
        keys=("center_x","track_top","track_bottom","fill_top","edge_uncertainty")
        if any(type(g.get(k)) is not int for k in keys):raise ObservationError("bar geometry must be integer pixels")
        top,bottom,fill,unc=(g[k] for k in ("track_top","track_bottom","fill_top","edge_uncertainty"))
        height=bottom-top
        if (g["center_x"]<0 or top<0 or height<16 or not top<=fill<=bottom
            or unc<0 or unc>3 or height<=2*unc):
            raise ObservationError("invalid bar geometry")
        filled=bottom-fill
        estimate=round(100*filled/height,1)
        low=max(0,math.floor(100*max(0,filled-unc)/(height+2*unc)))
        high=min(100,math.ceil(100*min(height,filled+unc)/(height-2*unc)))
        return {"reading_kind":kind,"confidence":"VISUAL_UNCALIBRATED",
                "graphical_fill_estimate_pct":estimate,"graphical_fill_range_pct":[low,high],
                "hp_numeric_percent":None,"full_state":"NOT_NEAR_FULL" if high<90 else "UNKNOWN",
                "identity_evidence":entry["identity_evidence"],"geometry_px":{k:g[k] for k in keys}}
    if kind in {"USER_APPROX_PERCENT","USER_EXACT_PERCENT"}:
        if source_kind not in {"USER_REPORT","USER_CORRECTION"}:
            raise ObservationError("numeric HP must be directly user reported, not inferred from bar")
        val=entry.get("reported_percent")
        if type(val) is not int or not 0<=val<=100:
            raise ObservationError("reported HP percent must be integer 0..100")
        is_exact=kind=="USER_EXACT_PERCENT"
        return {"reading_kind":kind,"confidence":"USER_EXACT" if is_exact else "USER_APPROX",
                "graphical_fill_estimate_pct":None,"graphical_fill_range_pct":None,
                "hp_numeric_percent":val,"full_state":("FULL" if is_exact and val==100 else
                  "NOT_FULL" if val<100 else "UNKNOWN"),"identity_evidence":"USER_NAMED_PLAYER"}
    raise ObservationError("unrecognized HP reading; use VERTICAL_BAR or direct user percent")

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
        mid=e.get("target_match_id")
        if mid:
            if not isinstance(patch,dict) or set(patch)!={"opponent"} or not isinstance(patch["opponent"],str) or not patch["opponent"]:
                raise ObservationError("match-wide correction permits only nonempty opponent")
            touched=False
            for item in base.values():
                if item["kind"]=="MATCH_ATTEMPT" and item.get("match_id")==mid:
                    item["opponent"]=patch["opponent"];touched=True
                elif item["kind"]=="MATCH_SCHEDULE":
                    entries=[]
                    for entry in item.get("entries",[]):
                        entry=dict(entry)
                        if entry.get("match_id")==mid:entry["opponent"]=patch["opponent"];touched=True
                        entries.append(entry)
                    item["entries"]=entries
            if not touched:raise ObservationError("match-wide correction target unknown")
            continue
        if target not in base or not isinstance(patch,dict) or not patch:
            raise ObservationError("correction needs earlier target and nonempty patch")
        if "entries" in patch:
            if (base[target]["kind"]!="HP_OBSERVATION" or set(patch)!={"entries"} or
                e["source"]["kind"]!="USER_CORRECTION" or not isinstance(patch["entries"],list) or
                not patch["entries"]):
                raise ObservationError("HP correction must be user-sourced entries for HP_OBSERVATION")
            base[target]["entries"]=patch["entries"]
            base[target]["hp_corrected_by_event_id"]=e["event_id"]
            continue
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
    active=[];discarded=[];discarded_match_ids=set();rollback_count=0;unknown_after_rollback=False
    for e in events:
        if e["kind"]!="ROLLBACK":
            active.append(e)
            continue
        cp=e.get("to_checkpoint_id") or e.get("restore_to_event_id")
        if cp is None:
            discarded.extend(x["event_id"] for x in active if x["kind"]!="ROLLBACK")
            discarded_match_ids.update(x.get("match_id") for x in active if x["kind"]=="MATCH_ATTEMPT")
            active=[e];unknown_after_rollback=True;rollback_count+=1
            continue
        if not isinstance(cp,str) or not cp:
            raise ObservationError(f"{e['event_id']}: invalid rollback anchor")
        index=next((i for i,v in enumerate(active)
            if v["event_id"]==cp and (v["kind"]=="SAVE_CHECKPOINT" or
               (v["kind"]=="SCREEN" and v.get("is_savepoint") is True))),None)
        if index is None:
            raise ObservationError(f"{e['event_id']}: rollback anchor is not an explicit active savepoint")
        removed=active[index+1:]
        discarded.extend(x["event_id"] for x in removed if x["kind"]!="ROLLBACK")
        discarded_match_ids.update(x.get("match_id") for x in removed if x["kind"]=="MATCH_ATTEMPT")
        active=active[:index+1]+[e]
        rollback_count+=1
    return active,discarded,discarded_match_ids,rollback_count,unknown_after_rollback

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
    active,discarded,reverted_match_ids,rollback_count,unknown_after_rollback=resolve_active_lineage(corrected)
    prior_first={}
    for e in corrected:
        if e["kind"]=="MATCH_ATTEMPT" and e.get("attempt")==1 and e.get("match_id") not in prior_first:
            prior_first[e["match_id"]]={"attempt":1,"our_runs":e.get("our_runs"),
                "their_runs":e.get("their_runs"),"evidence_id":e["event_id"]}
    state={"schema_version":"1.2","last_event_seq":len(events),"period_floor":None,
           "last_seen_screen_period":None,
           "resources":{"fresh":False,"values":None,"last_observed":None},
           "matches":{},"completed_match_periods":[],"skills":[],
           "training_counts_by_player_drill":{},"training_counts_observed":{},"training_history":[],
           "item_effects":[],"item_uses":[],"inventory":{"fresh":False,"items":None},
           "observations_ignored_as_stale":[],"reverted_event_ids":discarded,
           "discarded_branch_event_ids":discarded,"rollback_count":rollback_count,
           "timeline_status":"UNKNOWN_AFTER_ROLLBACK" if unknown_after_rollback else "TRUSTED",
           "hp_by_player":{},
           "current_exact_time":"UNKNOWN"}
    floor=None;closed=set();matches={};seen_attempts=set()
    last_mutation_id=None;last_screen_clock=None;last_screen_period=None;last_context_event_id=None
    def invalidate():
        state["resources"]["fresh"]=False
        state["resources"]["values"]=None
        state["inventory"]["fresh"]=False
        state["inventory"]["items"]=None
        for value in state["hp_by_player"].values():value["fresh"]=False
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
            after=e.get("observed_after_event_id") or e.get("after_event_id")
            mutation_unresolved=last_mutation_id is not None
            if (historical or e.get("branch")!="ACCEPTED" or
                (mutation_unresolved and after!=last_mutation_id) or
                (pk in closed and after!=last_mutation_id)):
                state["observations_ignored_as_stale"].append(eid)
                continue
            current_clock=clock_minutes(e.get("clock"))
            if last_screen_period==pk and last_screen_clock is not None and current_clock is not None and current_clock<last_screen_clock and not e.get("confirmed_clock_reset"):
                state["observations_ignored_as_stale"].append(eid)
                continue
            state["last_seen_screen_period"]=pk
            state["resources"]={"fresh":True,"values":{k:vals[k] for k in COUNTERS},"last_observed":eid}
            inventory=e.get("inventory")
            if inventory is not None:
                if not isinstance(inventory,dict) or any(not isinstance(k,str) or type(v) is not int or v<0 for k,v in inventory.items()):
                    raise ObservationError(f"{eid}: invalid inventory")
                state["inventory"]={"fresh":True,"items":dict(inventory)}
            if state["timeline_status"]=="UNKNOWN_AFTER_ROLLBACK":
                state["timeline_status"]="RECAPTURED_AFTER_UNANCHORED_ROLLBACK"
            state["current_exact_time"]=e.get("clock") or "UNKNOWN"
            floor=max(floor,p) if floor else p
            last_screen_clock=current_clock;last_screen_period=pk;last_mutation_id=None;last_context_event_id=eid
        elif kind=="HP_OBSERVATION":
            entries=e.get("entries")
            if not isinstance(entries,list) or not entries:
                raise ObservationError(f"{eid}: HP requires one or more entries")
            # Always validate data, including historical/rejected screenshots.
            parsed={}
            for entry in entries:
                result=measure_hp_observation(entry,e["source"]["kind"])
                player=entry["player"].strip()
                if player in parsed:raise ObservationError(f"{eid}: duplicated HP player")
                parsed[player]=result
            after=e.get("after_event_id") or e.get("observed_after_event_id")
            clock=clock_minutes(e.get("clock"))
            stale=(historical or e.get("branch")!="ACCEPTED" or
                   (last_context_event_id is not None and after!=last_context_event_id) or
                   (pk in closed and last_mutation_id is None and e.get("confirmed_after_period_completion") is not True) or
                   (last_screen_period==pk and last_screen_clock is not None and
                    clock is not None and clock<last_screen_clock and not e.get("confirmed_clock_reset")))
            if stale:
                state["observations_ignored_as_stale"].append(eid)
                continue
            for player,result in parsed.items():
                state["hp_by_player"][player]={**result,"fresh":True,"event_id":eid,"period":pk,
                    "source_locator":e["source"]["locator"],"hp_corrected_by_event_id":e.get("hp_corrected_by_event_id")}
            last_context_event_id=eid
            floor=max(floor,p) if floor else p
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
                    invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid;last_context_event_id=eid
                    floor=max(floor,p) if floor else p
        elif kind=="MATCHES_COMPLETED":
            if e["source"]["kind"] not in {"USER_REPORT","USER_CORRECTION"}:
                raise ObservationError(f"{eid}: period completion requires user assertion")
            closed.add(pk)
            for m in matches.values():
                if m["period"]==pk and m["status"]=="SCHEDULED":m["status"]="COMPLETED_SCORE_UNKNOWN"
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid;last_context_event_id=eid
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
                per=state["training_counts_observed"].setdefault(player,{})
                per[drill]=per.get(drill,0)+1
            state["training_history"].append({"event_id":eid,"drill":drill,"participants":list(players),
                "drill_level":e.get("drill_level"),"cheer":e.get("cheer")})
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid;last_context_event_id=eid
                floor=max(floor,p) if floor else p
        elif kind=="ITEM_USE":
            if e.get("branch")!="ACCEPTED":continue
            bundle=e.get("item_bundle") or e.get("items")
            if not isinstance(bundle,list) or not bundle or any(
                not isinstance(x,dict) or not isinstance(x.get("item",x.get("name")),str) or not x.get("item",x.get("name")) or
                type(x.get("quantity")) is not int or x["quantity"]<1 for x in bundle):
                raise ObservationError(f"{eid}: item use needs item_bundle with positive quantity")
            bundle=[{"item":x.get("item",x.get("name")),"quantity":x["quantity"]} for x in bundle]
            delta=e.get("effect_deltas",e.get("observed_delta",{}))
            if not isinstance(delta,dict) or any(not isinstance(k,str) or type(v) is not int for k,v in delta.items()):
                raise ObservationError(f"{eid}: invalid effect_deltas")
            item_entry={"event_id":eid,"item_bundle":bundle,"effect_deltas":delta}
            state["item_effects"].append(item_entry)
            state["item_uses"].append(item_entry)
            if not historical:
                invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid;last_context_event_id=eid
                floor=max(floor,p) if floor else p
        elif kind=="ROLLBACK":
            invalidate();state["current_exact_time"]="UNKNOWN";last_mutation_id=eid;last_context_event_id=eid
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
    if state.get("timeline_status")=="UNKNOWN_AFTER_ROLLBACK":
        errors.append("UNRESOLVED_ROLLBACK")
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
    if action_type=="ITEM":
        items=rec.get("items")
        if not isinstance(items,list) or not items:
            errors.append("ITEM_SELECTION_REQUIRED")
            items=[]
        if not state.get("inventory",{}).get("fresh"):
            errors.append("ITEM_INVENTORY_NOT_VERIFIED")
        else:
            for item in items:
                if (not isinstance(item,dict) or not isinstance(item.get("item"),str) or
                    type(item.get("quantity")) is not int or item["quantity"]<1 or
                    state["inventory"]["items"].get(item["item"],0)<item["quantity"]):
                    errors.append("INSUFFICIENT_ITEM_INVENTORY")
    # A bar's fill ratio is never an exact HP value without a live calibration.
    hp_claims=rec.get("hp_claims",{})
    if not isinstance(hp_claims,dict):
        errors.append("INVALID_HP_CLAIMS")
        hp_claims={}
    for player,claim in hp_claims.items():
        obs=state.get("hp_by_player",{}).get(player)
        if not obs or not obs["fresh"]:
            errors.append(f"HP_NOT_VERIFIED:{player}")
            continue
        if claim=="FULL" and obs["full_state"]!="FULL":
            errors.append(f"HP_FULL_NOT_PROVEN:{player}")
        elif claim=="NEAR_FULL":
            if obs["reading_kind"]=="VERTICAL_BAR":
                code="HP_NEAR_FULL_CONTRADICTED" if obs["full_state"]=="NOT_NEAR_FULL" else "HP_NEAR_FULL_NOT_PROVEN"
                errors.append(f"{code}:{player}")
            elif obs["hp_numeric_percent"]<90:
                errors.append(f"HP_NEAR_FULL_CONTRADICTED:{player}")
        elif claim not in {"FULL","NEAR_FULL","NOT_FULL"}:
            errors.append(f"UNSUPPORTED_HP_CLAIM:{player}")
    limits=rec.get("hp_min_by_player",{})
    if not isinstance(limits,dict):
        errors.append("INVALID_HP_REQUIREMENTS")
        limits={}
    for player,minimum in limits.items():
        obs=state.get("hp_by_player",{}).get(player)
        if type(minimum) is not int or not 0<=minimum<=100:
            errors.append(f"INVALID_HP_THRESHOLD:{player}")
        elif not obs or not obs["fresh"]:
            errors.append(f"HP_NOT_VERIFIED:{player}")
        elif obs["reading_kind"]!="USER_EXACT_PERCENT":
            errors.append(f"HP_THRESHOLD_UNVERIFIED:{player}")
        elif obs["hp_numeric_percent"]<minimum:
            errors.append(f"HP_BELOW_THRESHOLD:{player}")
    mid=rec.get("target_match_id")
    if mid:
        m=state["matches"].get(mid)
        if m is None:errors.append("UNKNOWN_MATCH")
        elif m["status"]!="SCHEDULED" or m["period"] in state["completed_match_periods"]:
            errors.append("ALREADY_COMPLETED_MATCH")
        else:
            if action_type=="MATCH" and m["period"]!=rec.get("target_period"):
                errors.append("MATCH_PERIOD_CONFLICT")
            if state.get("period_floor") and m["period"]<state["period_floor"]:
                errors.append("PAST_PERIOD_MATCH")
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
