#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
from typing import Any

VALIDATOR_VERSION = "1.0.0"
IMPLEMENTED_SYSTEM_GUARDS = {"VERSION","PROVENANCE","UNKNOWN","ELIGIBILITY"}
IMPLEMENTED_RULES = {"GR-001","IR-001","IR-003"}
ALLOWED_EVIDENCE_KINDS = {"RAW_EVIDENCE","USER_ASSERTION","INTERPRETED_OBSERVATION","VERIFIED_DERIVATION","ARCHIVE","EXTERNAL"}
ALLOWED_FACT_TYPES = {"OBSERVED","DERIVED","HYPOTHESIS","UNKNOWN"}

class ValidationError(Exception): pass

def load_json_yaml(path: Path) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc: raise ValidationError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON-compatible YAML: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(65536),b""): h.update(chunk)
    return h.hexdigest()

def git(*args: str) -> str:
    p=subprocess.run(["git",*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode: raise ValidationError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()

def changed_paths(parent_sha: str, head_sha: str) -> set[str]:
    return {x.strip() for x in git("diff","--name-only",parent_sha,head_sha).splitlines() if x.strip()}

def load_parent_json_yaml(parent_sha: str, path: str) -> Any|None:
    p=subprocess.run(["git","show",f"{parent_sha}:{path}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode: return None
    try: return json.loads(p.stdout)
    except json.JSONDecodeError as exc: raise ValidationError(f"parent {path} invalid JSON-compatible YAML: {exc}") from exc

def parse_decision_log(path: Path) -> list[dict[str,Any]]:
    try: lines=path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc: raise ValidationError(f"missing required file: {path}") from exc
    out=[]
    for n,raw in enumerate(lines,1):
        if not raw.strip(): continue
        try: item=json.loads(raw)
        except json.JSONDecodeError as exc: raise ValidationError(f"{path}:{n} invalid JSONL: {exc.msg}") from exc
        if not isinstance(item,dict): raise ValidationError(f"{path}:{n} must be a JSON object")
        out.append(item)
    return out

def enabled(policy,name): return bool(policy.get("system_guards",{}).get(name,{}).get("enabled",False))
def rule_enabled(policy,rule_id): return bool(policy.get("rules",{}).get(rule_id,{}).get("enabled",False))

def validate_policy_coverage(policy):
    errors=[]
    for name,spec in policy.get("system_guards",{}).items():
        if spec.get("enabled") and name not in IMPLEMENTED_SYSTEM_GUARDS:
            errors.append(f"enabled system guard is not implemented: {name}")
    for rid,spec in policy.get("rules",{}).items():
        if spec.get("enabled") and spec.get("enforcement")=="VALIDATOR" and rid not in IMPLEMENTED_RULES:
            errors.append(f"enabled validator rule is not implemented: {rid}")
    return errors

def check_version(ledger,logs,mode,checked_sha):
    errors=[]
    version=ledger.get("ledger_version")
    if not isinstance(version,int) or version<1: errors.append("ledger_version must be integer >=1")
    if ledger.get("schema_version")!="1.0": errors.append("unsupported ledger schema_version")
    seqs=[r.get("seq") for r in logs]
    if any(not isinstance(s,int) for s in seqs): errors.append("DECISION_LOG seq values must be integers")
    elif seqs and seqs!=list(range(1,len(seqs)+1)): errors.append("DECISION_LOG seq must be contiguous starting at 1")
    if mode=="guard":
        actual=git("rev-parse","HEAD")
        if actual!=checked_sha: errors.append(f"checked_sha mismatch: arg={checked_sha} git_head={actual}")
        parent=git("rev-parse","HEAD^")
        changed=changed_paths(parent,actual)
        if "CURRENT_RUN_LEDGER.yaml" in changed:
            if ledger.get("expected_parent_sha")!=parent:
                errors.append(f"stale ledger parent: expected_parent_sha={ledger.get('expected_parent_sha')} actual_parent={parent}")
            previous=load_parent_json_yaml(parent,"CURRENT_RUN_LEDGER.yaml")
            if previous is None:
                if version!=1: errors.append("first ledger commit must use ledger_version=1")
            else:
                pv=previous.get("ledger_version")
                if not isinstance(pv,int): errors.append("parent ledger_version is invalid")
                elif version!=pv+1: errors.append(f"ledger_version must increment by exactly 1: parent={pv} current={version}")
            if not logs: errors.append("ledger change requires DECISION_LOG record")
            else:
                last=logs[-1]
                if last.get("ledger_version")!=version: errors.append(f"last DECISION_LOG ledger_version must equal current ledger_version={version}")
                if last.get("expected_parent_sha")!=parent: errors.append("last DECISION_LOG expected_parent_sha must match actual parent")
    return errors

def check_provenance(ledger,policy):
    errors=[]; evidence=ledger.get("evidence",[])
    if not isinstance(evidence,list): return ["evidence must be a list"]
    by_id={}
    for item in evidence:
        if not isinstance(item,dict): errors.append("every evidence entry must be an object"); continue
        eid=item.get("evidence_id"); kind=item.get("kind")
        if not isinstance(eid,str) or not eid: errors.append("evidence_id must be non-empty string"); continue
        if eid in by_id: errors.append(f"duplicate evidence_id: {eid}"); continue
        by_id[eid]=item
        if kind not in ALLOWED_EVIDENCE_KINDS: errors.append(f"{eid}: invalid evidence kind {kind!r}")
        if kind=="RAW_EVIDENCE" and not item.get("locator"): errors.append(f"{eid}: RAW_EVIDENCE requires locator")
        if kind=="USER_ASSERTION" and not item.get("statement"): errors.append(f"{eid}: USER_ASSERTION requires statement")
        if kind in {"INTERPRETED_OBSERVATION","VERIFIED_DERIVATION"}:
            refs=item.get("source_refs")
            if not isinstance(refs,list) or not refs: errors.append(f"{eid}: {kind} requires source_refs")
    for eid,item in by_id.items():
        refs=item.get("source_refs",[]) or []
        for ref in refs:
            if ref not in by_id: errors.append(f"{eid}: missing source evidence ref {ref}")
        if rule_enabled(policy,"IR-003") and item.get("kind")=="INTERPRETED_OBSERVATION":
            if not any(by_id.get(ref,{}).get("kind")=="RAW_EVIDENCE" for ref in refs):
                errors.append(f"{eid}: IR-003 requires at least one RAW_EVIDENCE source")
    facts=ledger.get("facts",[])
    if not isinstance(facts,list): errors.append("facts must be a list"); return errors
    seen=set()
    for fact in facts:
        if not isinstance(fact,dict): errors.append("every fact entry must be an object"); continue
        fid=fact.get("fact_id"); ftype=fact.get("fact_type")
        if not isinstance(fid,str) or not fid: errors.append("fact_id must be non-empty string"); continue
        if fid in seen: errors.append(f"duplicate fact_id: {fid}")
        seen.add(fid)
        if ftype not in ALLOWED_FACT_TYPES: errors.append(f"{fid}: invalid fact_type {ftype!r}")
        if ftype!="UNKNOWN":
            refs=fact.get("source_refs")
            if not isinstance(refs,list) or not refs: errors.append(f"{fid}: non-UNKNOWN fact requires source_refs")
            else:
                for ref in refs:
                    if ref not in by_id: errors.append(f"{fid}: missing evidence ref {ref}")
    eligibility=ledger.get("eligibility",{})
    if not isinstance(eligibility,dict): errors.append("eligibility must be an object")
    else:
        for key,entry in eligibility.items():
            if not isinstance(entry,dict): errors.append(f"eligibility.{key} must be an object"); continue
            refs=entry.get("source_refs")
            if not isinstance(refs,list) or not refs: errors.append(f"eligibility.{key} requires source_refs")
            else:
                for ref in refs:
                    if ref not in by_id: errors.append(f"eligibility.{key}: missing evidence ref {ref}")
    return errors

def check_unknown(ledger):
    errors=[]
    facts=ledger.get("facts",[])
    for fact in facts if isinstance(facts,list) else []:
        if isinstance(fact,dict) and fact.get("fact_type")=="UNKNOWN":
            if fact.get("value") is not None: errors.append(f"{fact.get('fact_id')}: UNKNOWN fact must have value=null")
            if fact.get("usable_for_decision") is not False: errors.append(f"{fact.get('fact_id')}: UNKNOWN fact cannot be usable_for_decision")
    unknowns=ledger.get("unknowns",[])
    if not isinstance(unknowns,list): return ["unknowns must be a list"]
    ids=set(); blocking=[]
    for item in unknowns:
        if not isinstance(item,dict): errors.append("every unknown entry must be an object"); continue
        uid=item.get("unknown_id")
        if not isinstance(uid,str) or not uid: errors.append("unknown_id must be non-empty string"); continue
        if uid in ids: errors.append(f"duplicate unknown_id: {uid}")
        ids.add(uid)
        if item.get("status") not in {"OPEN","RESOLVED"}: errors.append(f"{uid}: status must be OPEN or RESOLVED")
        if item.get("status")=="OPEN" and item.get("material_to_next_action") is True: blocking.append(uid)
    gate=ledger.get("current_gate",{})
    if blocking:
        if not isinstance(gate,dict) or gate.get("status")!="BLOCKED_UNKNOWN":
            errors.append("material OPEN unknowns require current_gate.status=BLOCKED_UNKNOWN")
        refs=set(gate.get("reason_refs",[])) if isinstance(gate,dict) else set()
        missing=[u for u in blocking if u not in refs]
        if missing: errors.append("current_gate.reason_refs missing material unknowns: "+", ".join(missing))
    return errors

def check_eligibility(ledger,policy):
    errors=[]; year=ledger.get("time",{}).get("year"); elig=ledger.get("eligibility",{})
    k=elig.get("koshien_y1") if isinstance(elig,dict) else None
    if rule_enabled(policy,"GR-001") and year==1:
        if not isinstance(k,dict): errors.append("GR-001 requires eligibility.koshien_y1")
        elif k.get("eligible") is not False: errors.append("GR-001 violation: Y1 Koshien eligible must be false")
    if isinstance(elig,dict):
        for key,entry in elig.items():
            if not isinstance(entry,dict): continue
            d,e,a=entry.get("displayed"),entry.get("eligible"),entry.get("available_now")
            if a is True and e is not True: errors.append(f"eligibility.{key}: available_now=true requires eligible=true")
            if rule_enabled(policy,"IR-001") and d is True and e is False and a is not False:
                errors.append(f"IR-001 violation at eligibility.{key}: displayed=true must not imply available_now")
    return errors

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True); p.add_argument("--sha",required=True)
    p.add_argument("--mode",choices=["guard","reference"],default="guard"); p.add_argument("--json-out")
    a=p.parse_args(); root=Path.cwd(); checks={}; errors=[]
    try:
        ledger=load_json_yaml(root/"CURRENT_RUN_LEDGER.yaml"); policy=load_json_yaml(root/"RUN_GUARD_POLICY.yaml"); logs=parse_decision_log(root/"DECISION_LOG.jsonl")
        errors += [f"POLICY: {e}" for e in validate_policy_coverage(policy)]
        funcs={"VERSION":lambda:check_version(ledger,logs,a.mode,a.sha),"PROVENANCE":lambda:check_provenance(ledger,policy),"UNKNOWN":lambda:check_unknown(ledger),"ELIGIBILITY":lambda:check_eligibility(ledger,policy)}
        for name,func in funcs.items():
            if enabled(policy,name):
                es=func(); checks[name]={"status":"PASS" if not es else "FAIL","errors":es}; errors += [f"{name}: {e}" for e in es]
            else: checks[name]={"status":"DISABLED","errors":[]}
        ok=not errors
        result_name=("PASS" if ok else "FAIL") if a.mode=="guard" else ("REFERENCE_PASS" if ok else "REFERENCE_FAIL")
        result={"contract_version":policy.get("validator_contract",{}).get("contract_version","1.0"),"result":result_name,"guard_verified":bool(ok and a.mode=="guard"),"mode":a.mode.upper(),"repository":a.repo,"checked_sha":a.sha,"ledger_version":ledger.get("ledger_version"),"policy_version":policy.get("policy_version"),"validator_version":VALIDATOR_VERSION,"ledger_sha256":sha256_file(root/"CURRENT_RUN_LEDGER.yaml"),"policy_sha256":sha256_file(root/"RUN_GUARD_POLICY.yaml"),"checks":checks,"errors":errors}
    except ValidationError as exc:
        result={"contract_version":"1.0","result":"FAIL" if a.mode=="guard" else "REFERENCE_FAIL","guard_verified":False,"mode":a.mode.upper(),"repository":a.repo,"checked_sha":a.sha,"ledger_version":None,"policy_version":None,"validator_version":VALIDATOR_VERSION,"checks":checks,"errors":[str(exc)]}
    if a.json_out: Path(a.json_out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
    print(f"RGV {result['result']} | policy={result.get('policy_version')} | ledger={result.get('ledger_version')} | sha={result.get('checked_sha')} | validator={result.get('validator_version')}")
    if a.mode=="reference": print("GUARD_NOT_VERIFIED | reference-mode does not establish formal Guard PASS")
    return 0 if result["result"] in {"PASS","REFERENCE_PASS"} else 1

if __name__=="__main__": raise SystemExit(main())
