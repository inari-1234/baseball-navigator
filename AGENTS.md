# AGENTS.md — Baseball Navigator Boot Contract

## Purpose
This repository is the canonical handoff for 野球部ものがたり. Do not reconstruct strategy from chat memory when the repository is available.

## Mandatory BOOT on a new chat or after losing context
Before giving gameplay advice, read in this order:
1. `RUN_GUARD_POLICY.yaml`
2. `CURRENT_RUN_LEDGER.yaml`
3. the tail of `DECISION_LOG.jsonl`
4. `SAPPORO_SPRINT_STRATEGY.md`

Then state internally which run/gate is active and use that state as the baseline.

## Evidence precedence
Current live screen / current user report > current ledger evidence > current strategy document > archived Authority / older handoff > public external material.
A newer user report can supersede older saved state, but the repository must be checkpointed later if the change matters to the run.

## FAST operating mode
After BOOT, do not re-scan the repository, Library, or web on every turn.
Use the already-loaded current state plus the newest user delta and answer the next action first.
Re-scan only when one of these occurs:
- conflicting evidence,
- an OPEN material unknown,
- a strategy redesign question,
- a mechanics claim needs verification,
- the user explicitly requests a re-scan.

Normal live-play replies should prioritize:
1. next action,
2. exact three special-training participants when applicable,
3. target skill / ability,
4. whether to SAVE/LOAD retry or accept,
5. only the minimum reasoning needed.

## Handoff rule
Do not ask the user to paste a long handoff into a new chat. A one-line instruction to boot this repository is sufficient.

## Current strategy mode
The active planned mode is `Y1_OCTOBER_SAPPORO_SPRINT` as defined in `CURRENT_RUN_LEDGER.yaml` and `SAPPORO_SPRINT_STRATEGY.md`.
The previous run is abandoned for redesign; the next gate is to reset the game and capture the new-run initial state.

## Reset semantics
- Special-training skill reroll via SAVE/LOAD: allowed and strategically used for targeted core skills.
- Practice-match reset: prohibited when the match is being used as a combat gate.
- Required official match: at most one selective reload for a close, clearly stochastic loss; do not grind through a structural mismatch.
- Reset-assisted wins are never classified as stable clears.

## State persistence / Run Guard
Gameplay discussion alone does not require a commit.
When a state-changing checkpoint is persisted:
- update `CURRENT_RUN_LEDGER.yaml` and append `DECISION_LOG.jsonl` in the same commit,
- increment `ledger_version` exactly by 1,
- set `expected_parent_sha` to the actual parent commit,
- preserve evidence classes and UNKNOWN semantics,
- never self-certify Guard PASS,
- verify the GitHub Actions `Run Guard` result after push.

## Avoided failure mode
Do not create logic in files and then ignore it in conversation. The BOOT sequence is the activation mechanism; FAST mode is the latency control mechanism.
