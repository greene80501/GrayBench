# Offline campaign planning

campaign-plan constructs the frozen Protocol and CampaignSetup from a ModelSpec, pinned cache,
immutable image and explicit selection. Choose normal, hard or both complete suites with --suite,
or repeat --task with exact suite/task keys. Duplicates and unknown keys are rejected. The builder
does not select tasks based on model answers or reference compatibility, and does not filter
external-service tasks from a full suite. Its result lists known external task keys for review.

The plan records exact public request digests, selected task identities, per-task judge-manifest
identities, runtime image and full engine source identity. Analysis is conservatively bound to
the entire engine source, including the summary implementation. Optional system text and repeat
count are explicit. Private test and reference source are not embedded in the setup JSON.

Planning performs no provider discovery or generation and exclusively creates its output file.
Tests check offline behavior, private-source separation, duplicate selection and overwrite refusal.
A separate offline check loaded both real pinned datasets and froze all 302 public requests:
151 normal and 151 hard. That check used an explicitly unverified placeholder model identifier;
it is not evidence that a live model exists or can execute the full suites.

The development workflow is campaign-plan, campaign-create, then repeated campaign-step calls,
followed by summary/verify-ledger. Deferred steps return a timestamp; unresolved deliveries or
judgments require explicit adjudication rather than retrying blindly. Creating a plan does not
establish task adequacy or model capability. Model discovery/drift policy, full interface fidelity,
reviewed admission and statistical reporting remain required before release certification.
