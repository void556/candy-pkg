import sys
import os
import json
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import shutil

# Directories
CANDY_BASE_DIR = r"C:\Candy"
CANDY_APPS_DIR = r"C:\Candy\apps"
CONFIG_FILE = os.path.join(CANDY_BASE_DIR, "config.json")

# Default official trusted outlets
DEFAULT_CONFIG = {
    "outlets": [
        "https://candy-pkg.pages.dev/apps/"
    ],
    "require_checksum": True,      # Reject binaries if SHA-256 doesn't match
    "enforce_trusted_outlets": True # Safety check: Block unknown HTTP domains
}

TRUSTED_DOMAINS = [
    "candy-pkg.pages.dev",
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com"
]


def init_environment():
    """Ensure base directories and config file exist."""
    os.makedirs(CANDY_BASE_DIR, exist_ok=True)
    os.makedirs(CANDY_APPS_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)


def load_config():
    """Load configuration options and outlets."""
    init_environment()
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG


def save_config(cfg):
    """Save configuration options."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


def is_url_safe(url: str, cfg: dict) -> bool:
    """Security Check: Verify domain safety against known/trusted outlets."""
    if not cfg.get("enforce_trusted_outlets", True):
        return True

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()

    for trusted in TRUSTED_DOMAINS:
        if domain == trusted or domain.endswith("." + trusted):
            return True
    return False


def verify_sha256(file_path: str, expected_hash: str) -> bool:
    """Calculate and compare SHA-256 hash of a downloaded file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        calculated = sha256.hexdigest().lower()
        return calculated == expected_hash.lower()
    except Exception as e:
        print(f"[!] Hash calculation failed: {e}")
        return False


def fetch_json(url: str):
    """Fetch JSON data from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Candy-CLI"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def download_file(url: str, dest_path: str):
    """Download binary with progress feedback."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Candy-CLI"})
        with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"[!] Download error: {e}")
        return False


def cmd_install(app_identifier: str, load_file: str = None):
    cfg = load_config()
    manifest = None

    # 1. Fetch Manifest
    if load_file:
        print(f"[*] Loading local manifest: {load_file}")
        if os.path.exists(load_file):
            with open(load_file, "r") as f:
                manifest = json.load(f)
        else:
            print(f"[!] Manifest file '{load_file}' not found.")
            return
    else:
        print(f"[*] Searching for '{app_identifier}' across outlets...")
        for outlet in cfg.get("outlets", []):
            manifest_url = f"{outlet.rstrip('/')}/{app_identifier}.json"
            manifest = fetch_json(manifest_url)
            if manifest:
                print(f"[+] Found manifest at {manifest_url}")
                break

    if not manifest:
        print(f"[!] Could not find package manifest for '{app_identifier}'.")
        return

    # Extract Manifest Data
    name = manifest.get("name", app_identifier)
    download_url = manifest.get("url")
    bin_name = manifest.get("bin")
    expected_sha256 = manifest.get("sha256")

    if not download_url or not bin_name:
        print("[!] Invalid manifest: Missing 'url' or 'bin' attributes.")
        return

    # 2. Safety Verification (URL Check)
    print(f"[*] Safety Verification: Checking download origin...")
    if not is_url_safe(download_url, cfg):
        print(f"\n[🔒 SECURITY ALERT] Refused to download from unverified origin:")
        print(f"    URL: {download_url}")
        print("    This source is not in the trusted domain list.")
        confirm = input("    Do you want to force install anyway? (y/N): ").strip().lower()
        if confirm != "y":
            print("[!] Installation cancelled for security.")
            return

    # 3. Download Binary
    target_path = os.path.join(CANDY_APPS_DIR, bin_name)
    temp_path = target_path + ".tmp"

    print(f"[*] Downloading {name} executable...")
    if not download_file(download_url, temp_path):
        print("[!] Download failed.")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return

    # 4. SHA-256 Checksum Verification
    print("[*] Verifying package integrity (SHA-256)...")
    if expected_sha256:
        if verify_sha256(temp_path, expected_sha256):
            print("[+] SHA-256 checksum verified successfully! File is safe.")
        else:
            print(f"\n[⚠️ CHECKSUM MISMATCH DETECTED]")
            print(f"    Expected: {expected_sha256}")
            print(f"    Calculated hash does not match!")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print("[!] Aborting installation due to possible corruption or tampering.")
            return
    else:
        if cfg.get("require_checksum", True):
            print("[!] SECURITY WARNING: Manifest lacks a 'sha256' checksum!")
            confirm = input("    Proceed with unverified binary installation? (y/N): ").strip().lower()
            if confirm != "y":
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                print("[!] Installation cancelled.")
                return
        else:
            print("[!] Notice: No SHA-256 hash provided in manifest. Skipping hash check.")

    # Move binary to final location
    if os.path.exists(target_path):
        os.remove(target_path)
    os.rename(temp_path, target_path)

    # Save installed package tracking file
    record_file = os.path.join(CANDY_APPS_DIR, f"{name}.manifest.json")
    with open(record_file, "w") as f:
        json.dump(manifest, f, indent=4)

    print(f"\n[🎉] Successfully installed {name} to {target_path}")


def cmd_remove(app_name: str):
    record_file = os.path.join(CANDY_APPS_DIR, f"{app_name}.manifest.json")
    if not os.path.exists(record_file):
        print(f"[!] Package '{app_name}' is not installed.")
        return

    with open(record_file, "r") as f:
        manifest = json.load(f)

    bin_name = manifest.get("bin")
    bin_path = os.path.join(CANDY_APPS_DIR, bin_name) if bin_name else None

    if bin_path and os.path.exists(bin_path):
        os.remove(bin_path)
        print(f"[+] Removed binary: {bin_path}")

    os.remove(record_file)
    print(f"[+] Successfully uninstalled {app_name}.")


def cmd_list():
    init_environment()
    files = os.listdir(CANDY_APPS_DIR)
    manifests = [f for f in files if f.endswith(".manifest.json")]

    if not manifests:
        print("No packages installed via Candy.")
        return

    print("\nInstalled Packages:")
    print("-" * 50)
    for m_file in manifests:
        path = os.path.join(CANDY_APPS_DIR, m_file)
        try:
            with open(path, "r") as f:
                data = json.load(f)
                name = data.get("name", m_file.replace(".manifest.json", ""))
                version = data.get("version", "unknown")
                desc = data.get("description", "")
                print(f"• {name} (v{version}) - {desc}")
        except Exception:
            continue
    print("-" * 50)


def cmd_outlet(action: str = None, url: str = None):
    cfg = load_config()
    outlets = cfg.get("outlets", [])

    if action == "list" or not action:
        print("\nConfigured Candy Outlets:")
        for o in outlets:
            print(f" - {o}")
    elif action == "add" and url:
        if not url.startswith("http"):
            url = "https://" + url
        if not url.endswith("/"):
            url += "/"
        if url not in outlets:
            outlets.append(url)
            cfg["outlets"] = outlets
            save_config(cfg)
            print(f"[+] Added outlet: {url}")
        else:
            print(f"[!] Outlet already exists.")
    elif action == "remove" and url:
        outlets = [o for o in outlets if url not in o]
        cfg["outlets"] = outlets
        save_config(cfg)
        print(f"[+] Removed outlet matching '{url}'")


def print_help():
    print("""
Candy Package Manager (CLI)

Usage:
  candy install <app_name>              Install package from outlets
  candy install --load <path.json>      Install package from local manifest
  candy remove <app_name>               Remove an installed package
  candy list                            List installed packages
  candy outlet [list|add|remove] [url]  Manage outlets
""")


def main():
    init_environment()
    args = sys.argv[1:]

    if not args:
        print_help()
        return

    cmd = args[0].lower()

    if cmd == "install":
        if len(args) > 2 and args[1] == "--load":
            cmd_install(app_identifier="", load_file=args[2])
        elif len(args) >= 2:
            cmd_install(app_identifier=args[1])
        else:
            print("[!] Specify an app name or use --load <manifest.json>")
    elif cmd == "remove":
        if len(args) >= 2:
            cmd_remove(args[1])
        else:
            print("[!] Specify an app name to remove.")
    elif cmd == "list":
        cmd_list()
    elif cmd == "outlet":
        action = args[1] if len(args) > 1 else "list"
        url = args[2] if len(args) > 2 else None
        cmd_outlet(action, url)
    else:
        print_help()


if __name__ == "__main__":
    main()
