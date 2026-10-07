# In-place array geometry updates

The standalone graph now applies bounded array metadata changes while retaining
the existing Python ndarray object and underlying storage. Owners and views can
change shape and strides; numeric arrays can reinterpret their dtype while
preserving their total byte count. Existing held views retain their own metadata.
Object-array reshaping keeps its actual referenced objects.

Owning arrays remain within the admitted contiguous-storage forms. Their metadata
transition first uses a contiguous layout covering the full allocation. A native
probe showed why a zero-stride temporary is unsafe for owners: NumPy then rejects
restoring the original strides because its validation uses the reduced address
span. Views instead use their fixed owner bounds and a zero-stride intermediate.
For a different numeric element width, a small contiguous final axis permits
reinterpretation without flattening a reversed or broadcast outer layout.
The final shape and strides come only from already validated records.

No buffer is replaced or resized. Base references, offsets and total byte counts
cannot change for exported arrays. Those forms remain explicitly unsupported,
along with external buffers, structured dtypes and custom subclasses. These
limits avoid invalidating existing aliases; they are not scored as wrong answers.
All record validation, including late malformed references, precedes any mutation.

## Verification

The first geometry run had 13 expected unsupported-capability failures and two
passing controls. New tests now cover owner/view reshapes, Fortran layout changes,
negative and zero strides, different numeric element widths and endianness,
readonly arrays, empty arrays, retained views and rejected late malformed state.
The old blanket-geometry-rejection test was updated to assert the newly supported
reshape behavior. Storage resizing still has an explicit rejection regression.
The three focused array files passed 77 tests. The full Docker-enabled suite
passed **654 tests** in 187.55 seconds without failures, errors or skips.
Local JUnit artifact: outputs/GrayBench-v4-array-geometry-full-tests.xml.
Lint and formatting checks passed.

The final standalone Linux probe passed 18 checks in the pinned image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Twelve dependency modules and the fixture were mounted read-only, with no
network, user 65534, 512 MiB memory, one CPU, 64 PIDs and 16 MiB temporary storage.
Actual source and probe bytes were checked against the reported hashes.
[Final raw result](GrayBench-v4-array-geometry-final-linux-probe.json) SHA-256:
b7d1e3af45a225ab0a297746a8ad067ad09a8ea9ff297e788e241c15611ad2cc.
The earlier probe is retained; the final probe incorporates a module-docstring
correction describing newly supported metadata changes.

The standalone Linux probe also exercises dtype/shape updates with a held view
whose original dtype and object identity must survive. This remains a development
probe, not a protected candidate/oracle replay. No production identity fix is
claimed before v4 integration and protected admission.

## Remaining scope

Scientific, primitive, symbolic and supported array components now have explicit
graph representations. Circuit components, exception-state synchronization, v4
worker/oracle integration and protected admission remain the next work. Overall
release eligibility remains false and no certified model score was generated.
