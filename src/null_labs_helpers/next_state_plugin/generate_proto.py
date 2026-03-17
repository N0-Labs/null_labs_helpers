import subprocess
import sys
from pathlib import Path


def _fix_grpc_imports(grpc_file: Path) -> None:
    """Rewrite generated absolute proto import to package-relative import."""
    text = grpc_file.read_text(encoding="utf-8")
    old = "import next_state_pb2 as next__state__pb2"
    new = "from . import next_state_pb2 as next__state__pb2"
    if old in text:
        grpc_file.write_text(text.replace(old, new), encoding="utf-8")


def main():
    here = Path(__file__).resolve().parent
    proto = here / "next_state.proto"
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{here}",
        f"--python_out={here}",
        f"--grpc_python_out={here}",
        str(proto),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"protoc failed: {result.stderr.strip()}")
    _fix_grpc_imports(here / "next_state_pb2_grpc.py")
    print("Generated gRPC stubs:", flush=True)
    print(str(here / "next_state_pb2.py"), flush=True)
    print(str(here / "next_state_pb2_grpc.py"), flush=True)


if __name__ == "__main__":
    main()
