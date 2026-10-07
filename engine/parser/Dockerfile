# Parser-only derivative. BuildKit must resolve this exact historical image.
# Candidate and oracle retain that image.
FROM graybench-qpy-base:2fc74bd3dd29@sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd

USER 0:0
COPY requirements.lock /tmp/parser-requirements.lock
RUN python -m pip install --no-cache-dir --no-deps --force-reinstall \
        --only-binary=:all: --require-hashes -r /tmp/parser-requirements.lock \
    && python -c "import qiskit; assert qiskit.__version__ == '2.5.2'"
USER 65534:65534
