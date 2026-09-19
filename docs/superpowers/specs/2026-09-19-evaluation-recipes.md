# Explicit evaluation recipes

The approved overhaul requires corrected, separately identified evaluation tracks
to work through the normal campaign lifecycle. Existing task 0, 82 and 141 judges
must be selectable without manually constructing a different scoring pipeline.

CampaignSetup will freeze one named evaluation recipe. Upstream remains the
default. The three existing revisions remain development-only and reject tasks
outside their supported family; there is no fallback or implicit filtering.
Task 141's public revision must happen before request hashes are frozen and be
reconstructed identically on resume. Other recipes preserve their public prompts.
All image, timeout, output and file-parser limits remain bound to judge manifests.

Campaign orchestration validates the selected track as well as dataset, request,
judge and runtime identities before dispatch. Context and reports identify the
recipe. Comparison uses the same revised task records as generation and rejects
incompatible protocols. A CLI-selected revision cannot become an upstream score.

Validation must cover offline planning, wrong task/recipe rejection, serialization
and reconstruction, changed-prompt rejection before dispatch, private-data
separation, protected judgment of saved answers, and comparison reconstruction.
Use deterministic transport fixtures for lifecycle tests; this change needs no
billable model generations. Preserve existing evidence and frozen-source rules.
