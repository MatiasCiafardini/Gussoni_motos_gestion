import requests
from pathlib import Path


def download_file(url: str, dest: Path, progress_cb=None):
    """
    Descarga un archivo desde `url` a `dest`.
    progress_cb(bytes_downloaded, total_bytes) opcional.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=10) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)

                if progress_cb:
                    progress_cb(downloaded, total)

    return dest
