"""QPY parsing outside the host and trusted oracle. Only typed data comes back."""

from graybench.sandbox import Candidate

DECODER = """def decode_artifact():
    from qiskit import qpy
    with open('/input/artifact.bin', 'rb') as source:
        circuits = qpy.load(source)
    return circuits
"""


def decode_qpy(data, *, image, docker, timeout=30, output_limit=1024 * 1024):
    # This process receives the artifact and codec, never candidate source or private tests.
    # A parser exploit cannot emit a trusted judgment. Its result is still untrusted wire data.
    with Candidate(
        DECODER,
        image=image,
        docker=docker,
        timeout=timeout,
        output_limit=output_limit,
        opaque_input=data,
    ) as decoder:
        result = decoder.call_wire("decode_artifact")
        return result["value"], {
            "active_seconds": decoder.active_seconds,
            "wire_response": result,
            "projection": "supported circuit structure and bounded JSON metadata",
        }
