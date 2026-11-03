#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

VALIDATOR_VERSION = "1.0.0"

class ValidationError(Exception):
    pass

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON {path}: line {exc.lineno}: {exc.msg}") from exc

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines=path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValidationError(f"missing required file: {path}") from exc
    out=[]
    for n,raw in enumerate(lines,1):
        if not raw.strip():
            continue
        try:
            item=json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid JSONL {path}:{n}: {exc.msg}") from exc
        if not isinstance(item,dict):
            raise ValidationError(f"{path}:{n} must be an object")
        out.append(item)
    return out

def validate_contract(contract: dict[str,Any]) -> list[str]:
    errors=[]
    if contract.get("schema_version")!="1.0": errors.append("unsupported contract schema_version")
    if contract.get("status")!="ACTIVE": errors.append("DECISION_CONTRACT status must be ACTIVE")
    rules=contract.get("rules")
    if not isinstance(rules,list) or not rules: return errors+["rules must be a non-empty list"]
    ids=[]
    for r in rules:
        if not isinstance(r,dict): errors.append("every rule must be an object"); continue
        rid=r.get("rule_id")
        if not isinstance(rid,str) or not rid: errors.append("rule_id must be non-empty string"); continue
        ids.append(rid)
        if r.get("status") not in {"ACTIVE","EXPERIMENTAL","SUPERSEDED","ARCHIVE_ONLY"}:
            errors.append(f"{rid}: invalid status {r.get('status')!r}")
        if r.get("status")=="ACTIVE" and not r.get("rule"):
            errors.append(f"{rid}: ACTIVE rule requires rule text")
    if len(ids)!=len(set(ids)): errors.append("duplicate rule_id in DECISION_CONTRACT")
    return errors

def validate_trace(contract: dict[str,Any], logs: list[dict[str,Any]], ledger: dict[str,Any]) -> list[str]:
    errors=[]
    cfg=contract.get("decision_log_enforcement",{})
    start=cfg.get("start_seq")
    if not isinstance(start,int) or start<1: return ["decision_log_enforcement.start_seq must be integer >=1"]
    modes=set(cfg.get("basis_modes",[]))
    rules={r.get("rule_id"):r for r in contract.get("rules",[]) if isinstance(r,dict)}
    active={rid for rid,r in rules.items() if r.get("status")=="ACTIVE"}
    all_ids=set(rules)
    for entry in logs:
        seq=entry.get("seq")
        if not isinstance(seq,int) or seq<start: continue
        basis=entry.get("decision_basis")
        if not isinstance(basis,dict):
            errors.append(f"seq {seq}: decision_basis required from seq {start}")
            continue
        mode=basis.get("mode")
        if mode not in modes:
            errors.append(f"seq {seq}: invalid decision_basis.mode {mode!r}")
            continue
        rule_ids=basis.get("rule_ids",[])
        if mode=="RULE_APPLIED":
            if not isinstance(rule_ids,list) or not rule_ids:
                errors.append(f"seq {seq}: RULE_APPLIED requires non-empty rule_ids")
            else:
                for rid in rule_ids:
                    if rid not in active: errors.append(f"seq {seq}: RULE_APPLIED references non-ACTIVE rule {rid!r}")
        elif mode=="RULE_OVERRIDDEN":
            if not isinstance(rule_ids,list) or not rule_ids:
                errors.append(f"seq {seq}: RULE_OVERRIDDEN requires rule_ids")
            else:
                for rid in rule_ids:
                    if rid not in all_ids: errors.append(f"seq {seq}: override references unknown rule {rid!r}")
            if not basis.get("reason"): errors.append(f"seq {seq}: RULE_OVERRIDDEN requires reason")
            if not basis.get("revisit_condition"): errors.append(f"seq {seq}: RULE_OVERRIDDEN requires revisit_condition")
        elif mode=="NO_RULE":
            if not basis.get("description"): errors.append(f"seq {seq}: NO_RULE requires description")
    cs=ledger.get("canonical_strategy",{})
    if cs.get("decision_contract")!="DECISION_CONTRACT.json":
        errors.append("CURRENT_RUN_LEDGER canonical_strategy.decision_contract must be DECISION_CONTRACT.json")
    return errors

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--json-out')
    args=ap.parse_args()
    errors=[]; checks={}
    try:
        contract=load_json(Path('DECISION_CONTRACT.json'))
        logs=load_jsonl(Path('DECISION_LOG.jsonl'))
        ledger=load_json(Path('CURRENT_RUN_LEDGER.yaml'))
        es=validate_contract(contract); checks['CONTRACT']={'status':'PASS' if not es else 'FAIL','errors':es}; errors+=es
        es=validate_trace(contract,logs,ledger); checks['TRACE']={'status':'PASS' if not es else 'FAIL','errors':es}; errors+=es
        result={'result':'PASS' if not errors else 'FAIL','validator_version':VALIDATOR_VERSION,'contract_version':contract.get('contract_version'),'checks':checks,'errors':errors}
    except ValidationError as exc:
        result={'result':'FAIL','validator_version':VALIDATOR_VERSION,'checks':checks,'errors':[str(exc)]}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.json_out: Path(args.json_out).write_text(text,encoding='utf-8')
    print(text,end='')
    return 0 if result['result']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
