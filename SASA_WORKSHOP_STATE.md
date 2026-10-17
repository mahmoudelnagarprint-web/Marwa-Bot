# SASA Workshop State - Mustafa (صاصا) Engineering Report

## System Discovery (Workshop PC)

**Host Information:**
- Working Directory: `G:\ai\Naggar Print POS Agent`
- Environment: Windows (likely Windows 10/11) with Python virtual environments
- Node ID: `WORKSHOP` (from .env file)

**Key Software Detected:**

1. **POS System Core** (`pos_system\`):
   - Backend API server (`backend.py`) exposing endpoints on port 7777
   - Frontend web UI (`web\`) served on port 8888 via Eel/Chrome app mode
   - Mobile API on port 7777 (Flask)
   - Laser queue management (`laser_engine.py`, `laser_ops.py`, `ui\laser_ops.py`)
   - Laser dashboard (`web\js\laser_dashboard.js`) for MES Kanban board
   - Database layer (`database.py`) with SQLite file at `G:\ai\Elnagar POS\pos_data.db` (referenced in .env)

2. **Laser Specific Components:**
   - `laser_engine.py`: LaserOpsEngine class handling queue summarization from 'Under Preparation' orders
   - `laser_ops.py`: Flet-based desktop UI for Laser Ops Center
   - `ui\laser_ops.py`: Main laser operations UI with Kanban board, product routing, material detection
   - `web\js\laser_dashboard.js`: Web-based laser dashboard (drag-drop, auto-refresh, filtering)
   - API endpoints: `/api/laser_queue`, `/api/laser_queue/upload`, `/api/laser_queue/done/<filename>`, `/api/laser_queue/images`, `/api/laser_queue/file/<filename>`
   - Image storage: `web\laser_images\` (created automatically)

3. **Automation / Integration:**
   - RDWorks integration via `orchestrator\agents\manufacturing_agent.py` and `system_worker.py` (generates RDWorks job files)
   - Production router (`pos_system\src\production_engine.py`) auto-detects laser workstation for products containing keywords: فانوس, بوكس, نتيجة, استاند, نوت بوك, نوتبوك, حفر, بصمة
   - Material detection for wood, acrylic, leather, etc.
   - Scrap-friendly detection for medals, chains, etc.

4. **Network Configuration (from pos_system\install_startup.bat):**
   - Static IP: `192.168.1.50` (adapter Ethernet or Wi-Fi)
   - Gateway: `192.168.1.1`
   - DNS: `8.8.8.8`, `1.1.1.1`
   - Firewall rules open ports: 7777 (backend), 7788 (mobile API), 8888 (UI)
   - Mobile app URL: `http://192.168.1.50:7788`
   - Backend API: `http://192.168.1.50:7777`
   - Desktop UI: `http://localhost:8888`

5. **Additional Systems:**
   - Telegram bot integration (`pos_system\telegram_bot\`) for order sync via WhatsApp
   - Google Sheets synchronization (`pos_system\google_sheet_sync_config.json`, `pos_system\google_api_sync.py`)
   - File operations engine (`pos_system\file_ops_engine.py`) for ingesting external folders into structured storage
   - Notebook smart system (`notebook\`) for voice/task capture

**Laser Machine Connection Status:**
- No direct laser controller DLL/EXE found in workshop scan.
- References to RDWorks suggest laser machine is controlled via RDWorks software.
- Expected laser machine IP per user note: `192.168.1.100` (USB or IP). Not yet verified.
- Backend currently runs on `192.168.1.50`; laser machine may be separate device on same network.

**Recommendations for Laser Connection:**
1. Verify physical laser machine is powered and connected to workshop PC via USB or Ethernet.
2. If USB: Check Device Manager for laser controller (likely appears as a serial or USB device).
3. If Ethernet: Assign static IP `192.168.1.100` on laser machine, ensure subnet mask `255.255.255.0`, gateway `192.168.1.1`.
4. Test connectivity: ping `192.168.1.100` from workshop PC.
5. RDWorks should detect laser machine upon launch; configure within RDWorks if needed.

## Self-Evolution & RPA (Robotic Process Automation) Opportunities

**Suggested Libraries for GUI Automation:**
- `PyAutoGUI`: Cross-platform, simple mouse/keyboard control, screenshot, image recognition.
- `Pywinauto`: Windows-specific, powerful for native Win32 controls (likely better for RDWorks, CorelDRAW, Photoshop).
- `OpenCV` + `numpy`: For template matching, OCR via Tesseract (pytesseract) to read screen text.
- `mouseinfo` or `pygetwindow`: For window management.
- `keyboard` and `mouse`: Low-level input.

**Existing Automation Clues in Codebase:**
- `orchestrator\agents\system_worker.py` already implements:
  - Screenshot capture via `mss`
  - Program launching (notepad/cmd/calc/explorer) and waiting for windows.
  - RDWorks integration: waiting for RDWorks window, reading button labels via UI automation (placeholder for future).
  - Clipboard operations for Photoshop.
- This suggests a foundation exists; we can extend `system_worker.py` with PyAutoGUI/Pywinauto for more robust RDWorks control.

**Ready-Made Agents / Frameworks on GitHub:**
- Search for: "PyAutoGUI RDWorks automation", "Pywinauto laser cutter", "open-source GUI automation Windows".
- Consider frameworks: `AgentGPT`, `BabyAGI`, `LangChain` agents for higher-level task planning (if needed later).
- For immediate needs, a simple script using PyAutoGUI to launch RDWorks, load a generated .rd file, and press Start is feasible.

**Proposed Action:**
1. Install PyAutoGUI and Pywinauto in the workshop Python environment (`.venv\Scripts\pip install pyautogui pywinauto`).
2. Create a test script in `pos_system\automation\` (or similar) to:
   - Launch RDWorks (path from `system_apps.json` or registry).
   - Wait for main window.
   - Load a test laser job file (generated by manufacturing_agent).
   - Press the Start button (image recognition or coordinate based).
   - Monitor completion via RDWorks status or file output.

## Documentation & State Tracking

**Created Files:**
- `SASA_WORKSHOP_STATE.md` (this file) – living document of workshop capabilities, configuration, and automation plan.
- `workshop_activities.log` – chronological log of all actions taken by Mustafa (see below).

**Next Steps for Documentation:**
- Keep `SASA_WORKSHOP_STATE.md` updated with any changes (new IP, software versions, laser machine details).
- Append to `workshop_activities.log` after each significant action (e.g., library installation, script test, laser connection verification).
- Consider adding a diagram of network layout (workshop PC, laser machine, mobile devices, etc.) in the state file.

## Immediate Actions Completed (as of this report)

1. Scanned workshop PC for POS system files, laser-related code, and configuration.
2. Reviewed backend (`backend.py`), laser engine (`laser_engine.py`), laser ops UI, and API endpoints.
3. Examined network configuration via `install_startup.bat` and `.env`.
4. Identified RDWorks integration points in orchestrator agents.
5. Created state and log files.

**Pending Actions:**
- Verify laser machine connectivity (ping/IP configuration).
- Install automation libraries (PyAutoGUI, Pywinauto, optionally OpenCV/pytesseract).
- Develop a prototype RDWorks automation script.
- Test end-to-end: generate laser job via POS, automate RDWorks to cut, confirm completion.

---
*Report generated by Mustafa (صاصا) on 2026-10-17. Under supervision of مروة and review by راصد.*