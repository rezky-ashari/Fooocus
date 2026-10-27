import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import re
import time
import atexit
import threading

_tunnel_process = None
_tunnel_url = None


def get_binary_path():
    # 1. Check if cloudflared is installed on system PATH
    sys_path = shutil.which("cloudflared")
    if sys_path:
        return sys_path

    # 2. Check local repo bin directory
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(repo_root, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    is_windows = sys.platform == "win32"
    bin_name = "cloudflared.exe" if is_windows else "cloudflared"
    local_path = os.path.join(bin_dir, bin_name)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000000:
        return local_path

    # 3. Download appropriate binary
    arch = platform.machine().lower()
    base_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/"

    if is_windows:
        download_url = base_url + "cloudflared-windows-amd64.exe"
    elif sys.platform.startswith("linux"):
        if "arm" in arch or "aarch64" in arch:
            download_url = base_url + "cloudflared-linux-arm64"
        else:
            download_url = base_url + "cloudflared-linux-amd64"
    elif sys.platform == "darwin":
        if "arm" in arch:
            download_url = base_url + "cloudflared-darwin-arm64.tgz"
        else:
            download_url = base_url + "cloudflared-darwin-amd64.tgz"
    else:
        raise OSError(f"Unsupported OS for automatic Cloudflare Tunnel download: {sys.platform}")

    print(f"[Cloudflare Tunnel] Downloading cloudflared binary from:\n  {download_url} ...", flush=True)
    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0 (Fooocus Cloudflare Tunnel)"}
        )
        with urllib.request.urlopen(req) as resp, open(local_path, "wb") as f:
            shutil.copyfileobj(resp, f)

        if not is_windows:
            os.chmod(local_path, 0o755)

        print(f"[Cloudflare Tunnel] Download complete: {local_path} ({os.path.getsize(local_path):,} bytes)", flush=True)
        return local_path
    except Exception as e:
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        raise RuntimeError(f"Failed to download cloudflared binary: {e}")


def _cleanup():
    global _tunnel_process
    if _tunnel_process and _tunnel_process.poll() is None:
        try:
            _tunnel_process.terminate()
            _tunnel_process.wait(timeout=3)
        except Exception:
            try:
                _tunnel_process.kill()
            except Exception:
                pass


atexit.register(_cleanup)


def start_tunnel(port=7865):
    """
    Starts a Cloudflare Tunnel in the background pointing to http://127.0.0.1:{port}
    and prints the public https://*.trycloudflare.com URL.
    """
    global _tunnel_process, _tunnel_url

    if _tunnel_process and _tunnel_process.poll() is None:
        return _tunnel_url

    binary_path = get_binary_path()
    cmd = [binary_path, "tunnel", "--url", f"http://127.0.0.1:{port}"]

    print(f"[Cloudflare Tunnel] Starting tunnel for http://127.0.0.1:{port} ...", flush=True)

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    _tunnel_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore",
        creationflags=creation_flags
    )

    url_event = threading.Event()

    def monitor_output():
        global _tunnel_url
        url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        for line in _tunnel_process.stderr:
            match = url_regex.search(line)
            if match and not _tunnel_url:
                _tunnel_url = match.group(0)
                url_event.set()
                print("\n" + "=" * 76, flush=True)
                print(f"[Cloudflare Tunnel] Connected! Stable public link:", flush=True)
                print(f"👉 {_tunnel_url}", flush=True)
                print("=" * 76 + "\n", flush=True)

    thread = threading.Thread(target=monitor_output, daemon=True)
    thread.start()

    # Wait up to 15 seconds for URL to appear
    url_event.wait(timeout=15.0)
    return _tunnel_url


if __name__ == "__main__":
    test_port = int(sys.argv[1]) if len(sys.argv) > 1 else 7865
    url = start_tunnel(test_port)
    if url:
        print(f"Tunnel is active: {url}", flush=True)
        _cleanup()
    else:
        print("Could not obtain Cloudflare Tunnel URL.", flush=True)
