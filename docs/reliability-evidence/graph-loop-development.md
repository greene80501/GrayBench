# Loop graph development

ForLoopOp, WhileLoopOp, BreakLoopOp and ContinueLoopOp now have fixed instruction
schemas. Original Python dictionaries, parameter containers and branch objects
remain separate from intrinsic cached parameters and branch snapshots. Held range
objects have their own immutable graph component, preserving equal-but-distinct
wrappers and start/stop/step descriptors without enumerating ranges.

Native loop index sets preserve range versus list behavior. Cached loop parameters
are reconstructed from fixed symbolic descriptors, yielding fresh native wrappers
rather than aliases to retained Python parameters. Compiled outer operations keep
fresh-wrapper behavior. Loops use the existing recursive branch operation/matrix
budgets; explicit index lists are bounded to 4096 values and integer descriptors
to 1024 bits. No arbitrary constructors or serialized Python code are introduced.

Eleven new regressions pass, including retained/cached divergence, compiled loops,
range identity, malformed state rejection before live mutation, and protected
parameterized loops with conditional breaks. Three initial regressions failed on
missing loop codecs; the initial while-loop fixture also revealed its own invalid
builder context and was corrected before the missing-codec failure was verified.

The source-guarded task150 reference replay passes both normal and hard. Raw file:
GrayBench-v4-loop-reference.jsonl. SHA256
4956114728d954b5777620e6bfcc4c91474e802d3a3b11b5a7cd8673a122e1b0;
chain head 7073524e088f72057531958b1bbdd540503ee562a5c41c49890fa9d0a0bc1b9e.
The complete event chain was independently inspected and its source manifest
exactly matched current runtime bytes. This is interface calibration, not a model
score or a whole-suite aggregate. Full Docker regression passed 914 tests in 354.94 seconds with zero failures,
errors or skips. Ruff lint/format (133 files), whitespace and secret-value checks
passed. Report: GrayBench-v4-loop-tests.xml.

Switch cases, circuit-owned classical variables/captures, remaining object
interfaces, uniform resource-policy calibration, full oracle admission, provider
calibration and reproduction remain required. Passing loop fixtures does not
certify the benchmark or establish complete Qiskit support.
