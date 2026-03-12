from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _http_ok(url: str, timeout_s: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    # During GROBID startup, the server may accept and immediately close connections.
    # Treat any transient connection error as "not ready yet" and keep polling.
    except Exception:
        return False


def ensure_grobid_container_running(
    *,
    container_name: str = "grobid",
    image: str = "grobid/grobid:0.8.2-full",
    host_port: int = 8070,
    container_port: int = 8070,
    ready_url: str | None = "http://localhost:8070/api/isalive",
    timeout_s: float = 180.0,
) -> None:
    """
    Ensure a Docker container named `container_name` is running.
    - If it exists, start it.
    - If it doesn't exist, create and run it.

    Raises RuntimeError with a clear message if Docker is not available or startup fails.
    """
    # Allow overriding image without code changes
    image = (os.environ.get("GROBID_DOCKER_IMAGE") or image).strip() or image

    # Check Docker is available
    v = _run(["docker", "version"])
    if v.returncode != 0:
        raise RuntimeError(
            "Docker is required to run GROBID. Please install and start Docker Desktop, "
            "then try again."
        )

    # Does container exist?
    exists = _run(
        ["docker", "ps", "-a", "--filter", f"name=^/{container_name}$", "--format", "{{.Names}}"]
    )
    if exists.returncode != 0:
        raise RuntimeError(f"Failed to query Docker containers: {exists.stderr.strip() or exists.stdout.strip()}")

    has_container = container_name in (exists.stdout or "").splitlines()

    if has_container:
        start = _run(["docker", "start", container_name])
        if start.returncode != 0:
            raise RuntimeError(f"Failed to start GROBID container: {start.stderr.strip() or start.stdout.strip()}")
    else:
        run = _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{host_port}:{container_port}",
                image,
            ]
        )
        if run.returncode != 0:
            raise RuntimeError(f"Failed to create GROBID container: {run.stderr.strip() or run.stdout.strip()}")

    if not ready_url:
        return

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _http_ok(ready_url, timeout_s=2.0):
            return
        time.sleep(1.0)

    logs = _run(["docker", "logs", "--tail", "50", container_name])
    tail = (logs.stdout or "").strip()
    raise RuntimeError(
        "GROBID container started but did not become ready in time. "
        f"Last logs:\n{tail}" if tail else "GROBID container started but did not become ready in time."
    )

