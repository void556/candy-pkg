# 🍬 Candy Package Manager

> A lightweight, decentralized Windows CLI package manager inspired by Scoop, designed for speed, simplicity, and safety.

⚠️ **Status: In Active Development**  
*Candy is currently in pre-release/experimental status. Features, manifest specs, and commands are subject to change as we build toward production stability.*

---

## 🛠️ How to Create an `app.json` Manifest

In Candy, every application is defined by a simple JSON manifest file hosted on a web registry or loaded locally.

### 1. Manifest Structure

Create a file named `<app_name>.json` (for example: `obs.json` or `notepadplusplus.json`):

```json
{
  "name": "obs",
  "version": "30.2.2",
  "description": "Free and open source software for video recording and live streaming",
  "url": "https://github.com/obsproject/obs-studio/releases/download/32.2.2/OBS-Studio-32.2.2-Windows-x64.zip",
  "sha256": "4d6e40e3ab155f56b30de517380566a206d74b63cdf5ad49aa596924768f97e1",
  "bin": "obs64.exe"
}
