# Large circuit transport calibration

The frozen 0a45d6a reference scan classified task 100 as a candidate error in both
suites when its circuit exceeded the wire-output limit. That classification did
not establish an incorrect answer. Wire overflow now yields an unsupported
interface outcome and suppresses aggregate accuracy. Diagnostic output flooding
continues to yield a candidate resource failure.

Large supported circuits use `compressed_circuit_v1`: lossless zlib compression
of the existing typed circuit JSON, without circuit optimization, repair or gate
removal. Limits are 64 MiB decoded JSON, 512 KiB compressed bytes and 1,000,000
instructions. Decoding checks declared size, stream completion, trailing data and
the underlying circuit schema. Serialization remains part of candidate active
time. These bounds do not establish universal circuit-interface coverage.

The targeted reference scan in `GrayBench-v3-large-circuit-reference.jsonl` passed
normal and hard task 100. It binds actual engine source hashes and is separate
from the historical full scan. Its SHA-256 is
`b42e8a0165c39b6496197781e455730e0e1e54e2f0b5f10d0cab9106c395c562`.
This is reference compatibility evidence, not an LLM score or proof of oracle
adequacy. Both suites still require task-by-task review.

Validation: 219 tests, zero failures/errors/skips with the immutable Docker test
image enabled. Added checks cover lossless 5,000-instruction reconstruction,
malformed and oversized compressed streams, wire overflow classification and
diagnostic flooding. The reference replay exercises a substantially larger real
Solovay-Kitaev decomposition through the protected judge.
