"""Native numeric ownership observations; no pointer dereferences or mutation of capsules."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import sys
import numpy as np
from scipy.linalg import expm

observations=[]
for dtype in (np.float32,np.float64,np.complex64,np.complex128):
    for n in (1,2,3,4):
        root=expm(np.zeros((n,n),dtype=dtype))
        view=root[::-1,::2]
        sibling=np.ndarray(root.shape,dtype=root.dtype,buffer=root)
        copied=root.copy()
        prior=root.copy()
        root.flags.writeable=False
        try:
            root.flags.writeable=True
            root_reenabled=True
        except ValueError:
            root_reenabled=False
        copied.flags.writeable=False
        copied.flags.writeable=True
        # A preexisting writable alias can still change a readonly root.
        sibling[0,0]=7
        assert root[0,0]==7
        assert view.base is root and sibling.base is root
        assert copied.flags.owndata and copied.base is None
        observations.append({'dtype':root.dtype.str,'dimension':n,'base_type':type(root.base).__name__,'owns_data':bool(root.flags.owndata),'slice_base_is_root':view.base is root,'buffer_view_base_is_root':sibling.base is root,'root_can_reenable_writeable':root_reenabled,'owning_copy_can_reenable_writeable':bool(copied.flags.writeable),'preexisting_alias_can_modify_root':bool(root[0,0]==7),'initial_identity_matrix':bool(np.array_equal(prior,np.eye(n)))})
        assert root_reenabled == (n==1)
result={'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'packages':{name:importlib.metadata.version(name) for name in ('numpy','scipy')},'observations':observations,'scope':'Pinned native expm outputs only. No general PyCapsule provenance or allocation-size inference. No arbitrary pointer access. Not protected benchmark scoring.'}
with Path(sys.argv[1]).open('x',encoding='utf-8',newline='\n') as stream:
    json.dump(result,stream,indent=2)
    stream.write('\n')
print(json.dumps({'observations':len(observations),'capsule_backed':sum(o['base_type']=='PyCapsule' for o in observations),'copy_semantics_differ':sum(not o['root_can_reenable_writeable'] for o in observations)}))
