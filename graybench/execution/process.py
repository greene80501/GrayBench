"""Capture bounded output without buffering arbitrary candidate output in memory."""

import subprocess
import threading


class OutputLimitExceeded(RuntimeError):
    pass


def run_bounded(args, *, timeout, limit, cwd=None, env=None):
    process = subprocess.Popen(
        args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()

    def drain(stream, buffer):
        try:
            while chunk := stream.read(8192):
                remaining = max(0, limit - len(buffer))
                buffer.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    exceeded.set()
                    process.kill()
        finally:
            stream.close()

    readers = [
        threading.Thread(target=drain, args=(stream, buffer), daemon=True)
        for stream, buffer in zip((process.stdout, process.stderr), buffers)
    ]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    finally:
        for reader in readers:
            reader.join(timeout=2)
    if exceeded.is_set():
        raise OutputLimitExceeded(f"Execution exceeded {limit} bytes per output stream")
    return subprocess.CompletedProcess(
        args,
        process.returncode,
        *(bytes(buffer).decode("utf-8", errors="replace") for buffer in buffers),
    )
