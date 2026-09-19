# Symbolic expressions and object-reference storage

This increment adds object-reference arrays and bounded ParameterExpression replay
to the standalone graph. SparsePauliOp can now retain its actual symbolic
coefficient array and coefficient object identities. DataBin validates the leading
shape of these arrays. This is development evidence, not protected v4 admission;
the [production identity defects](alias-boundary.md) remain unresolved.

Object arrays never send raw pointer bytes. Each owning slot contains a graph
scalar or reference; views contain an owning-array reference and checked geometry.
The pinned representation requires eight-byte slots, complete-slot offsets and
strides, and bounded owning storage. Numeric storage cannot serve as an object
array's base. Owners and views keep shape, strides, flags, shared storage and
independent identities. Negative/zero strides, transposes, readonly storage, cycles
and detached former children are covered. Scalar slot assignment avoids NumPy
coercing nested referenced objects into array dimensions. Cleared alignment flags
are preserved when addresses are safe; the flag cannot bypass address validation.

Expression replay uses a fixed arithmetic operation registry and bounded numeric
literals. It has a depth limit of 16, at most 512 steps per program and a 4096-unit
structural/operation budget. Integers are bounded to 1024 bits and numeric powers
to exponent magnitude 64. Unknown operations, invalid stack arity, nonfinite
results, conflicting parameter names and malformed references are rejected.
Reconstruction never evaluates a payload expression string: the only expression
string passed to the SDK is the fixed literal zero used to retain constant
ParameterExpression type.

Parameter descriptors returned by the SDK's replay getter are temporary wrappers.
Their values are encoded intrinsically; their actual vector references remain
graph edges. Thus shrinking a vector does not invalidate an expression that still
mentions detached elements, and expression getters keep referring to the same
vector after transport. Reconstructed expressions must encode back to the same
canonical replay record before admission, preventing silent representation changes.
Unsupported native operations/representations raise WireError rather than falling
back to value-only encoding.

## Verification

Twenty initial object-array tests failed because object dtypes were unsupported.
One test assumption was corrected: a cleared alignment flag is valid for safely
aligned storage and must be preserved, not rejected. Further boundary checks bring
this file to 22 tests. Ten initial expression tests failed at the missing codec;
additional adversarial cases bring that file to 18 tests. Separate RED regressions
caught noncanonical replay acceptance, an escaping SDK name-conflict exception,
and missing DataBin object-array shape validation. Those cases now pass.

The full Docker-enabled suite passed **634 tests** in 192.40 seconds with no
failures, errors or skips. Local JUnit artifact:
outputs/GrayBench-v4-symbolic-object-storage-full-tests.xml.
Ruff lint and the 100-file formatting check passed.

A supplementary native probe round-tripped nineteen arithmetic/unary/bound forms,
including reverse division/powers and complex constants. The automated cases cover
constant type, signed zero, cancellation parameter sets, complex values, vector
shrink and sparse coefficient identities.

The standalone Linux probe passed 17 checks in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Twelve explicit dependency modules and the fixture were mounted read-only with
no network, user 65534, 512 MiB memory, one CPU, 64 PIDs and 16 MiB temporary
storage. Source and probe hashes were checked against actual mounted bytes.
[Raw result](GrayBench-v4-symbolic-object-storage-linux-probe.json) SHA-256:
0bb379df198f0aa3f3f31a962c4ab79d6cacb83f64afd87b3d14c870d7e51075.

## Remaining work

Exported array geometry changes, external buffers, structured dtypes and custom
subclasses remain unsupported. Parameter-vector renaming remains unsupported.
Circuit/component graphs, v4 worker/oracle lifecycle integration and protected
reference/adversarial admission are unfinished. Overall release eligibility stays
false; no model generation or certified score was produced.
