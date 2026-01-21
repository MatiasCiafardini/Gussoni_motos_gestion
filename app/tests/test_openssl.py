from __future__ import annotations

import sys
from pathlib import Path
import subprocess

# Asegurar root del proyecto en PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.shared.openssl import get_openssl_path  # noqa: E402


def main() -> None:
    openssl = get_openssl_path()
    print("OpenSSL path:", openssl)

    result = subprocess.run(
        [str(openssl), "version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print("STDOUT:")
    print(result.stdout)

    print("STDERR:")
    print(result.stderr)

    print("RETURN CODE:", result.returncode)


if __name__ == "__main__":
    main()
