import os
import sys
import argparse
import urllib.request
import json
import shutil
import winreg
import ctypes

# Configuration
CANDY_DIR = r"C:\Candy"
APPS_DIR = os.path.join(CANDY_DIR, "apps")
CONFIG_FILE = os.path.join(CANDY_DIR, "config.json")
DEFAULT_REGISTRY = "https://candy-pkg.pages.dev/apps/{app_name}.json"

def load_config():
    """Load config.json or initialize defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(CANDY_DIR, exist_ok=True)
        default_config = {"outlets": [DEFAULT_REGISTRY]}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"outlets": [DEFAULT_REGISTRY]}

def save_config(config):
    """Save user configuration to disk."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def ensure_environment():
    """Ensure C:\\Candy\\apps exists and is permanently registered in User PATH."""
    if not os.path.exists(APPS_DIR):
        os.makedirs(APPS_DIR, exist_ok=True)

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""

        paths = [p.strip() for p in current_path.split(";") if p.strip()]
        if APPS_DIR not in paths:
            paths.append(APPS_DIR)
            new_path = ";".join(paths)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            
            # Broadcast setting change so active terminals pick up the updated PATH
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
            )
            print(f"[+] Added '{APPS_DIR}' to User PATH.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[!] Warning: Could not update PATH registry: {e}")

def download_file(url, target_path):
    """Download application binary with progress feedback."""
    print(f"[*] Downloading binary from: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Candy-Package-Manager/1.0'})
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("[+] Download complete.")
        return True
    except Exception as e:
        print(f"[!] Download failed: {e}")
        return False

def load_manifest_from_file_or_url(target):
    """Load manifest JSON from a local file path or remote HTTP(S) URL."""
    try:
        if target.startswith("http://") or target.startswith("https://"):
            req = urllib.request.Request(target, headers={'User-Agent': 'Candy-Package-Manager/1.0'})
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        
        if not os.path.exists(target):
            print(f"[!] Local config file not found: {target}")
            return None

        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
            
    except json.JSONDecodeError as e:
        print(f"[!] Invalid JSON format in '{target}': {e}")
        return None
    except Exception as e:
        print(f"[!] Failed to read config/manifest '{target}': {e}")
        return None

def fetch_manifest(app_name):
    """Scan configured outlets sequentially to locate the package manifest."""
    config = load_config()
    
    for outlet in config.get("outlets", [DEFAULT_REGISTRY]):
        manifest_url = outlet.format(app_name=app_name.lower())
        try:
            req = urllib.request.Request(manifest_url, headers={'User-Agent': 'Candy-Package-Manager/1.0'})
            with urllib.request.urlopen(req) as response:
                manifest_data = json.loads(response.read().decode('utf-8'))
                print(f"[+] Found package manifest at: {manifest_url}")
                return manifest_data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f"[!] HTTP Error {e.code} checking {outlet}")
        except Exception:
            continue
            
    print(f"[!] Package '{app_name}' not found across any configured outlets.")
    return None

def install_app(app_name=None, load_path=None):
    """Install a package via registry lookup OR loaded custom config JSON."""
    ensure_environment()

    if load_path:
        print(f"[*] Loading custom package config: {load_path}")
        manifest = load_manifest_from_file_or_url(load_path)
        if not manifest:
            return
        app_name = manifest.get("name", app_name or "custom_app")
    elif app_name:
        print(f"[*] Searching outlets for '{app_name}'...")
        manifest = fetch_manifest(app_name)
        if not manifest:
            return
    else:
        print("[!] Please specify an app name or use --load <path_to_json>.")
        return

    exe_filename = manifest.get("bin", f"{app_name}.exe")
    target_exe_path = os.path.join(APPS_DIR, exe_filename)

    print(f"[+] Package: {manifest.get('name', app_name)} (v{manifest.get('version', '1.0.0')})")
    if manifest.get("description"):
        print(f"    {manifest['description']}")

    if download_file(manifest['url'], target_exe_path):
        print(f"\n[🎉] Successfully installed '{app_name}'!")
        print(f"Executable path: {target_exe_path}")

def remove_app(app_name):
    """Remove an installed package executable."""
    target_exe = os.path.join(APPS_DIR, f"{app_name}.exe")
    if os.path.exists(target_exe):
        os.remove(target_exe)
        print(f"[+] Successfully removed '{app_name}'.")
    else:
        print(f"[!] Package '{app_name}' is not installed in {APPS_DIR}.")

def list_apps():
    """List installed packages in C:\\Candy\\apps."""
    if not os.path.exists(APPS_DIR):
        print("No packages installed yet.")
        return

    files = [f for f in os.listdir(APPS_DIR) if f.endswith(".exe")]
    if not files:
        print("No packages installed in C:\\Candy\\apps.")
        return

    print("Installed packages:")
    for f in files:
        print(f" - {os.path.splitext(f)[0]}")

def handle_outlet(args):
    """Manage custom outlets (PPAs/registries)."""
    config = load_config()
    
    if args.action == "add":
        url = args.url
        if "{app_name}" not in url:
            if not url.endswith("/"):
                url += "/"
            url += "apps/{app_name}.json"
            
        if url in config["outlets"]:
            print(f"[!] Outlet already exists: {url}")
            return
            
        config["outlets"].append(url)
        save_config(config)
        print(f"[+] Successfully added outlet: {url}")

    elif args.action == "list":
        print("Configured Candy Outlets:")
        for outlet in config.get("outlets", []):
            print(f" - {outlet}")

def main():
    parser = argparse.ArgumentParser(prog="candy", description="Candy CLI Package Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Subcommand: candy install [app_name] [--load / -l config.json]
    cmd_install = subparsers.add_parser("install", help="Install a package")
    cmd_install.add_argument("app_name", nargs="?", default=None, help="Name of the package")
    cmd_install.add_argument("-l", "--load", help="Path or URL to custom app config JSON file")

    # 2. Subcommand: candy remove <app_name>
    cmd_remove = subparsers.add_parser("remove", help="Remove an installed package")
    cmd_remove.add_argument("app_name", help="Name of the package to remove")

    # 3. Subcommand: candy list
    subparsers.add_parser("list", help="List installed packages")

    # 4. Subcommand: candy outlet <add/list>
    cmd_outlet = subparsers.add_parser("outlet", help="Manage custom package outlets (PPAs)")
    outlet_subparsers = cmd_outlet.add_subparsers(dest="action", required=True)
    
    cmd_outlet_add = outlet_subparsers.add_parser("add", help="Add a custom outlet URL")
    cmd_outlet_add.add_argument("url", help="URL of the outlet (e.g. https://my-registry.pages.dev/)")
    
    outlet_subparsers.add_parser("list", help="List all configured outlets")

    args = parser.parse_args()

    if args.command == "install":
        install_app(app_name=args.app_name, load_path=args.load)
    elif args.command == "remove":
        remove_app(args.app_name)
    elif args.command == "list":
        list_apps()
    elif args.command == "outlet":
        handle_outlet(args)

if __name__ == "__main__":
    main()