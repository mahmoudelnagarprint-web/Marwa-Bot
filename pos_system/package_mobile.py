
import os
import shutil
import glob
from datetime import datetime

def package_mobile():
    print("🚀 Starting Mobile App Packaging...")
    
    # 1. Detection Logic
    preferred = "mobile_app_stable_v0.8.0.py"
    candidate = None
    latest_time = 0

    if os.path.exists(preferred):
        candidate = preferred
        latest_time = os.path.getmtime(preferred)
        print(f"✅ Using preferred mobile source: {candidate} (Modified: {datetime.fromtimestamp(latest_time)})")
    else:
        py_files = glob.glob("*.py")
        for f in py_files:
            if f in ['package_mobile.py', 'kill_zombies.py', 'main.py']:
                continue
            try:
                with open(f, 'r', encoding='utf-8') as content:
                    text = content.read()
                    if 'import flet' in text or 'from flet' in text:
                        mtime = os.path.getmtime(f)
                        if mtime > latest_time:
                            latest_time = mtime
                            candidate = f
            except:
                continue

        if not candidate:
            print("❌ Error: Could not detect a Flet-based mobile app file.")
            return

        print(f"✅ Detected target file: {candidate} (Modified: {datetime.fromtimestamp(latest_time)})")

    # 2. Create Isolation Folder
    build_dir = "mobile_build_ready"
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)
    
    # 3. Smart Move & Rename
    shutil.copy2(candidate, os.path.join(build_dir, "main.py"))
    print(f"📦 Renamed {candidate} to {build_dir}/main.py")

    # 4. Create GitHub Workflows
    workflow_path = os.path.join(build_dir, ".github", "workflows")
    os.makedirs(workflow_path)
    
    workflow_content = """name: Build Flet APK
on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Flet
        run: |
          pip install flet
          
      - name: Flet Build APK
        uses: flet-dev/flet-build-action@v1
        with:
          build-type: apk
          project-path: .

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: app-release
          path: build/apk/*.apk
"""
    with open(os.path.join(workflow_path, "build_apk.yml"), "w", encoding="utf-8") as wf:
        wf.write(workflow_content)
    print("🤖 GitHub Workflow created.")

    # 5. Dependencies
    with open(os.path.join(build_dir, "requirements.txt"), "w", encoding="utf-8") as rf:
        rf.write("flet\nrequests\npillow\n")
    print("📄 requirements.txt created.")

    # 6. Assets
    if os.path.exists("assets"):
        shutil.copytree("assets", os.path.join(build_dir, "assets"))
        print("📂 Assets folder copied.")

    print("\n" + "="*40)
    print("✨ SUCCESS: Package is ready in 'mobile_build_ready'")
    print("👉 Open the 'mobile_build_ready' folder to start the upload.")
    print("="*40)

if __name__ == "__main__":
    package_mobile()
