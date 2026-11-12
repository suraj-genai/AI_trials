from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


APP = Path("/app")
TESTS = Path("/tests")
BUILD_DIR = Path("/tmp/firmware_allocator_verifier")
CANDIDATE_BUILD_DIR = BUILD_DIR / "candidate"
BINARY = BUILD_DIR / "allocator_harness"

MAX_TOTAL_SCORE = 50000 
WORKLOAD_NAMES = (
    "instructions_1.txt",
    "instructions_2.txt",
    "instructions_3.txt",
)

def _first_existing(*paths: Path) -> Path:
    """Return the first existing file from the supplied paths."""
    for path in paths:
        if path.is_file():
            return path
    rendered = "\n".join(f"  - {path}" for path in paths)
    raise AssertionError(f"Required verifier input was not found. Checked:\n{rendered}")


def _first_existing_dir(*paths: Path) -> Path:
    """Return the first existing directory from the supplied paths."""
    for path in paths:
        if path.is_dir():
            return path
    rendered = "\n".join(f"  - {path}" for path in paths)
    raise AssertionError(f"Required verifier directory was not found. Checked:\n{rendered}")


def _layout() -> tuple[Path, Path, Path, Path]:
    """Return candidate dir, trusted reference dir, workloads dir, repo root."""
    if (APP / "allocator.c").is_file() and (APP / "metadata.c").is_file():
        candidate_dir = APP
        reference_dir = TESTS / "reference"
        workloads_dir = reference_dir / "workloads"
        repo_root = APP
    else:
        # Local source-tree layout used while developing the task.
        repo_root = Path(__file__).resolve().parents[1]
        candidate_dir = _first_existing_dir(
            repo_root / "solution",
            repo_root / "environment" / "data",
        ).resolve()
        reference_dir = repo_root / "tests" / "reference"
        workloads_dir = reference_dir / "workloads"

    return candidate_dir, reference_dir, workloads_dir, repo_root


def _safe_environment() -> dict[str, str]:
    """Return a minimal environment for subprocesses to avoid agent-injected libraries and other interference."""
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "HOME": "/tmp",
    }


def _compile_harness() -> tuple[Path, Path]:
    """Compile the trusted harness and return the binary path and workloads directory."""
    candidate_dir, reference_dir, workloads_dir, repo_root = _layout()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_BUILD_DIR.mkdir(parents=True, exist_ok=True)

    candidate_files = (
        "allocator.c",
        "allocator.h",
        "metadata.c",
        "metadata.h",
    )
    for filename in candidate_files:
        source = _first_existing(candidate_dir / filename)
        shutil.copyfile(source, CANDIDATE_BUILD_DIR / filename)

    trusted_firmware = _first_existing(reference_dir / "firmware_mem.c")
    trusted_ground_truth = _first_existing(reference_dir / "ground_truth.c")
    trusted_harness = _first_existing(reference_dir / "test_harness.c")

    gcc = _first_existing(Path("/usr/bin/gcc"), Path("/bin/gcc"))
    command = [
        str(gcc),
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror=implicit-function-declaration",
        "-Werror=return-type",
        "-fno-common",
        "-fstack-protector-strong",
        "-I",
        str(reference_dir),
        "-I",
        str(CANDIDATE_BUILD_DIR),
        str(trusted_firmware),
        str(trusted_ground_truth),
        str(CANDIDATE_BUILD_DIR / "allocator.c"),
        str(CANDIDATE_BUILD_DIR / "metadata.c"),
        str(trusted_harness),
        "-o",
        str(BINARY),
    ]

    result = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=60,
        env=_safe_environment(),
        check=False,
    )
    assert result.returncode == 0, (
        "Trusted harness compilation failed.\n"
        f"Command: {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert workloads_dir.is_dir(), f"Trusted workload directory missing: {workloads_dir}"
    return BINARY, workloads_dir


def _expected_instruction_count(path: Path) -> int:
    """Return the expected instruction count for a workload file."""
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line and not line.startswith("#"):
                count += 1
    return count


def _run_workload(binary: Path, workload: Path) -> dict[str, int]:
    """Run the trusted harness on a workload and return the parsed RESULT payload."""
    result = subprocess.run(
        [str(binary), str(workload)],
        cwd=str(workload.parent),
        capture_output=True,
        text=True,
        timeout=60,
        env=_safe_environment(),
        check=False,
    )
    assert result.returncode == 0, (
        f"Trusted harness rejected {workload.name}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    result_lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT ")]
    assert len(result_lines) == 1, (
        f"Expected one machine-readable RESULT line for {workload.name}; "
        f"got stdout:\n{result.stdout}"
    )

    try:
        payload = json.loads(result_lines[0][len("RESULT "):])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Invalid RESULT JSON for {workload.name}: {result_lines[0]}") from exc

    expected_steps = _expected_instruction_count(workload)
    assert payload.get("instructions") == expected_steps, (
        f"{workload.name}: executed {payload.get('instructions')} instructions; "
        f"expected {expected_steps}"
    )
    return payload


def test_allocator_passes_trusted_workloads_and_score_target() -> None:
    """Verify workload completion, integrity, and performance requirements."""
    binary, workloads_dir = _compile_harness()

    workload_results: list[tuple[str, dict[str, int]]] = []
    for workload_name in WORKLOAD_NAMES:
        workload = _first_existing(workloads_dir / workload_name)
        payload = _run_workload(binary, workload)
        workload_results.append((workload_name, payload))

    total_score = sum(result["total_score"] for _, result in workload_results)
    total_instructions = sum(result["instructions"] for _, result in workload_results)

    for workload_name, result in workload_results:
        print(
            f"{workload_name}: instructions={result['instructions']}, "
            f"score={result['total_score']}, "
            f"metadata={result['metadata_score']}, "
            f"moves={result['total_moves']}"
        )

    print(
        f"TOTAL: instructions={total_instructions}, score={total_score}, "
        f"acceptance_limit={MAX_TOTAL_SCORE}"
    )

    assert total_score <= MAX_TOTAL_SCORE, (
        f"Total score {total_score} exceeds the frozen reference limit "
        f"{MAX_TOTAL_SCORE}. Correctness alone is not sufficient; reduce the "
        "combined metadata and movement penalty."
    )
