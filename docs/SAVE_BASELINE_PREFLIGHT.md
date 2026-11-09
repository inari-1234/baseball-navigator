# Current SAVE baseline preflight — observational origin only

## Goal

A screenshot of Y1 June PM5:20 was confirmed directly by the user to have been captured **immediately after loading a SAVE, before any game operation**. Its SHA-256 matches the already recorded source.

That fact anchors the visible post-load observations. It does **not** reveal which historical SAVE was loaded, whether prior matches/skills/training survived, or what player readiness/inventory is now. The provenance distinction remains mandatory.

## Read-only command

Run `python3 save_baseline_preflight.py --root .` after AGENTS Boot. It compares LIVE_EVENTS replay against CURRENT_LIVE_STATE and a direct ledger user-attestation, verifies the exact source hash and absence of later gameplay events, and checks that the unresolved rollback gate is still open.

The sole expected current result is `POSTLOAD_CAPTURE_VERIFIED_HISTORY_UNKNOWN`, with `rebaseline_ready=false`, `trusted_timeline=false`, `action_authorized=false` and `side_effects=false`.

This command does **not** append an event, manufacture a new checkpoint, set TRUSTED, reconstruct player HP, claim zero past training counts, or make historical match results live. No user screenshot bytes or private file paths enter GitHub.

## Next evidence and transition gate

The first no-resource-cost observation is opening **選手** and capturing the current player list and player status/skill information without training, item use, time advancement or SAVE reload. Confirm player identity, usable HP/condition and acquired skills against the loaded screen. Specific current total training counts remain UNKNOWN unless a direct explicit per-player/per-drill total is available; blank lists are not zero proof.

After that, cross-check current player readiness and confirmed match eligibility, and separately obtain complete inventory only if an item recommendation is considered. An action still needs source-verified local context, a current state revision, standard recommendation validation, and P7-E/F/G exact reply certification. A new tracking baseline should be a separate reviewed and tested transition with explicit lineage semantics, not a covert rewrite of prior evidence.

**Important:** Source-level evidence integrity and actual semantic game observation are different. The current main capture proves only the visible displayed fields plus the user's direct no-intervening-actions report; it does not prove all hidden historical state.

## Failure and regression cases

Run Guard must confirm a valid untrusted capture cannot become TRUSTED, a hedged/falsified user attestation is rejected, image-hash mismatches fail, stale event/snapshot mutations fail, no discarded training is counted, and this preflight writes no file. Historical events remain as audit only.

Use the verified capture only to choose the next **non-resource** evidence-gathering screen. No special training lineup, Cheer cost, fourth-session or item use is authorized.
