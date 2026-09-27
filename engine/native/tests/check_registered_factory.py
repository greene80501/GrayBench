"""The receiving graph needs a real native root and a registered capsule."""

import numpy as np
from scipy.linalg import _internal_matfuncs as native

for dtype in ("f", "d", "F", "D"):
    root = native._graybench_storage_new(dtype, (3, 3))
    assert type(root) is np.ndarray and root.shape == (3, 3)
    assert root.dtype.char == dtype
    assert not root.flags.owndata and root.base is not None
    assert native._graybench_storage_info(root.base) == (
        "scipy_matfuncs_v1",
        root.nbytes,
    )
    alias = root.view()
    replacement = np.full((3, 3), 2, dtype=root.dtype).tobytes()
    root.flags.writeable = False
    native._graybench_storage_write(root.base, replacement)
    assert np.all(root == 2) and np.all(alias == 2)
    assert not root.flags.writeable and alias.flags.writeable
    try:
        root.flags.writeable = True
    except ValueError:
        pass
    else:
        raise AssertionError("Native readonly root became writable")

boundary = native._graybench_storage_new("f", (2048, 2048))
assert boundary.nbytes == 16 * 1024 * 1024

for dtype, shape in (
    ("O", (2, 2)),
    ("d", (-1, 2)),
    ("d", (4096, 4096)),
    ("f", (2048, 2049)),
    ("d", (True, 2)),
    ("d", (np.int64(2), 2)),
    ("d", (2**128, 2)),
):
    try:
        native._graybench_storage_new(dtype, shape)
    except (TypeError, ValueError, MemoryError, OverflowError):
        pass
    else:
        raise AssertionError((dtype, shape))

print("Registered native factory contract passed")
