# P7-D: Verified reply boundary

## Intent and guarantee

The repository previously blocked a paid training candidate but allowed ChatGPT to independently describe historical participants and prices as a plan, or claim a current player's three accepted sessions without evidence. The P7-D reply guard deliberately certifies only exact source-pinned Japanese output templates for the canonical unknown-restored-SAVE SKILL and TRAINING_COUNTS responses.

check_reply.py implements render_guarded_reply(bridge_result, state) and check_reply(text, bridge, state, expected_main_sha, expected_event_seq). Any text different from the exact rendered template is REJECTED, including plausible extra explanation, invented counts, a conditional action, or an added numerical Cheer/Sports cost. An unsupported state returns NOT_CERTIFIED and cannot be silently converted into a safe reply. This is not a general Japanese-language truth detector.

## Integration

The source-pinned public P4 bridge continues to accept only the enum, opaque request ID, main commit SHA and event seq. Private chat text, images and user details are never submitted in a bridge request. For supported blocked SKILL or unknown TRAINING_COUNTS states, it adds safe_reply and safe_reply_check fields. A PASS certificate means only that the exactly displayed template passed the deterministic check at its pinned source; it does not certify any subsequently added ChatGPT prose.

Do not upload private free-text replies to public GitHub workflows. A local checkout may inspect a private draft using the check_reply.py CLI, with --bridge-result, --state, --reply, --expected-main-sha and --expected-event-seq. Use --render rather than --reply to display the grounded template. Rejection returns a nonzero exit code. If the agent has not invoked this check, it must not claim that it did.

This repository cannot intercept or enforce verification of all normal ChatGPT replies. It does not add an always-on ChatGPT runtime hook, cannot guarantee a connector call, and must not claim that it can.

## Open issues from the independent review

1. The P7-C TRAINING_COUNT_BASELINE accepts an explicit direct current-save user report. The engine cannot independently tell whether the user's recollection is hedged or mistaken. For a material baseline acceptance, require a clearly unqualified confirmation, scoped provenance, and a DECISION_LOG entry recording the evidence judgment. Tentative statements remain UNKNOWN. This is an operational requirement rather than machine-verified certainty.
2. The game's real fourth-popup counting unit is UNKNOWN: player alone, player/drill, drill level or something else. The program's player|drill key tracks accepted observations, not proof of a hidden game mechanic. Even a certified fourth session is not a guaranteed skill award.
3. Other intents, future TRUSTED states and free-form responses are outside P7-D certification until they receive explicit source-field rules, bounded templates and regression tests.

## Acceptance gate

CI must PASS all existing regressions and the new synthetic failure cases: a fabricated 3-session count, 'next is 4th', historical three-person lineup, Cheer ON/OFF plan, Sports6/Cheer20 costs, and even a valid template with appended text. Source SHA/event seq mismatch, unsuppressed candidate fields and unsupported statuses must fail closed; a verbatim canonical response must PASS. No current game events, resources, skills or inventory are modified.
