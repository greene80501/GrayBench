# Persistent candidate lifecycle control

The exact-commit 0a45d6a offline scan exposed a normal task-109 timeout at 122.27 seconds.
Its reference is a tiny parameterized circuit function, but the upstream oracle calls it
1,000 times. Starting separate Docker CLI processes for every pause and unpause dominated
the charged active wall time.

ContainerControl now opens one bounded local Docker API connection through the selected
context's Unix socket or Windows named pipe. It uses the pinned Docker Python SDK and keeps
the endpoint entirely outside candidate mounts. Candidate freeze, cumulative budget checks,
fail-closed cleanup and disjoint judge/candidate execution remain in place. The timing policy
identity changes to active-wall-v2-persistent-local-docker-control.

Separate task-109 replays pass all 1,000 calls in both suites. Normal took 38.16 seconds wall
and 34.29 seconds charged active time; hard took 41.51 seconds wall and 37.30 seconds active.
These are local compatibility/timing observations, not performance rankings or CPU accounting.
Lifecycle overhead remains charged and still requires calibration. Unit checks verify reuse
of one API client and rejection of unsupported remote endpoints. Existing Docker freeze and
cumulative-timeout checks also pass.

## Targeted replay artifact correction

Several scratch replay scripts accidentally retained the same matrix-replay.json output path.
Subsequent state-preparation, quantum-structure and task-109 runs overwrote that scratch artifact.
Their tool-output pass observations remain in the task history, but their original complete
wire transcripts were not retained separately. This is an evidence-retention defect.

The remaining task-109 artifact was copied to its correctly named persistent-control replay
file without deleting the original. Scratch scripts now use distinct names and refuse to start
if their output exists. A fresh source-byte-verified checkout of b6ca190 regenerated twelve
normal/hard cases (4, 5, 6, 45, 92, 108), all passing, into a new recovered-targeted artifact.
This is new evidence at b6ca190, not a claim to have recovered the lost original transcripts.
The independent full-suite scan at 0a45d6a uses a separate output and was unaffected.
