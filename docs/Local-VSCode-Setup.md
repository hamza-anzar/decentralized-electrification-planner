# Setting up VS Code + a local virtual environment (Windows)

This lets you open the project in VS Code and watch/run the notebooks and app locally, in your own `venv`, inside `D:\Claude Co Work\Code\Rural Electrification`.

Important: Claude cannot run commands on your computer in this session (file read/write only) — the steps below are for you to run yourself, once, in VS Code's terminal. Claude will keep building and testing everything in its own cloud environment and syncing finished, already-run files (including notebook outputs — charts and tables — baked in) into this folder as each step completes, so you can watch progress in VS Code even before your local venv exists.

## 1. Open the folder in VS Code

`File > Open Folder...` → select `D:\Claude Co Work\Code\Rural Electrification`.

## 2. Create the virtual environment

Open a terminal in VS Code (`` Ctrl+` ``, make sure it's a PowerShell or Command Prompt terminal, not WSL).

**Note on code blocks in these instructions:** the ```` ```powershell ```` / ```` ``` ```` lines you see wrapping commands are just markdown formatting (to show "this is code") — type only the commands inside, not the backtick lines themselves.

First, create the environment and install packages:

```
cd "D:\Claude Co Work\Code\Rural Electrification"
python -m venv venv
```

**Activating the venv** — Windows PowerShell blocks running the venv's activation script by default (a security setting called the execution policy), which is why `venv\Scripts\activate` fails with "running scripts is disabled on this system." This is normal and doesn't need an admin — pick ONE of these two options:

- **Option A — stay in PowerShell** (recommended, allows this terminal only, doesn't change any system-wide setting):
  ```
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  venv\Scripts\Activate.ps1
  ```
  You'll need to run the `Set-ExecutionPolicy` line again each time you open a fresh PowerShell terminal (it only applies to that one terminal session).

- **Option B — switch VS Code's terminal to Command Prompt instead** (click the dropdown next to the `+` in the terminal panel → "Command Prompt", or open a new terminal and select `cmd`), then:
  ```
  venv\Scripts\activate.bat
  ```
  (or just `venv\Scripts\activate` — cmd.exe resolves this fine, unlike PowerShell)

Either way, once activated you'll see `(venv)` at the start of the prompt. Then install the packages:

```
pip install -r requirements.txt
```

If `python` isn't recognized, you likely need Python 3.11+ installed from python.org first (check "Add python.exe to PATH" during install), then reopen the terminal.

This will take a few minutes the first time (installs pandas, streamlit, plotly, jupyter, etc. — the same set Claude is using in the cloud, pinned in `requirements.txt`).

## 3. Point VS Code at this venv

- Install the **Python** and **Jupyter** extensions from the VS Code Extensions marketplace, if not already installed.
- `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.\venv\Scripts\python.exe` (VS Code usually detects it automatically once created).
- When you open a notebook (`.ipynb`) file, click the **Select Kernel** button in the top-right of the notebook and choose the same `venv` interpreter.

## 3b. Troubleshooting: notebook picks a different kernel (e.g. "Python (catropy)" / a conda environment)

VS Code has **two separate environment pickers** that are easy to mix up: one for the **terminal** (`Python: Select Interpreter`), and one for **each notebook**, chosen individually in that notebook's own **Select Kernel** button — picking the interpreter for the terminal does not change which kernel a notebook uses, and vice versa. If a notebook shows something like "Python (catropy)" running, that's almost certainly a Conda/Anaconda environment VS Code auto-discovered on your machine (unrelated to this project) — it happens to be there and gets offered alongside `venv`, but it doesn't have this project's packages installed, so cells relying on pandas/openpyxl/etc. will fail or behave unexpectedly under it.

**Fix — register this project's venv as its own named kernel** (do this once, with the venv activated — see step 2 above for activating):

```
python -m ipykernel install --user --name=rural-electrification --display-name "Rural Electrification (venv)"
```

Then, for each notebook you open:

1. Click **Select Kernel** in the top-right of the notebook.
2. Choose **Select Another Kernel...** → **Jupyter Kernel...** (not "Python Environments...").
3. Pick **"Rural Electrification (venv)"** from the list. If it's not there yet, close and reopen the notebook, or run `Developer: Reload Window` from the Command Palette (`Ctrl+Shift+P`).

If you'd rather not register a named kernel, **Select Another Kernel... → Python Environments...** and pick `.\venv\Scripts\python.exe` directly also works — just make sure it's the one under this project's `venv\` folder, not a conda environment.

**Terminal commands not using the venv** is the separate picker: even with the right kernel selected for notebooks, a **new terminal** you open in VS Code starts in your system's default Python, not this venv, until you activate it — run the activation command from step 2 again in that terminal (`venv\Scripts\Activate.ps1` or `venv\Scripts\activate.bat`, whichever you used before) every time you open a fresh terminal tab. You'll know it's active when the prompt starts with `(venv)`.

## 4. Running the app locally

```powershell
venv\Scripts\activate
streamlit run app\Home.py
```

This opens the app in your browser at `http://localhost:8501`. Use the sidebar to move between the six steps — each
step's editable tables, Excel download/upload, charts, and a **Save** button that carries its results forward to the
next step (and updates the same `data\*.csv` files the notebooks use, so notebooks and app always agree).

If a page errors on `ModuleNotFoundError: No module named 'streamlit'` or similar, the venv likely isn't active in
that terminal — see the "Terminal commands not using the venv" note above.

On Step 4 (Solar PV & Battery), the "pvgis"/"nasa_power" live-fetch buttons need normal outbound internet access to
reach their APIs — they weren't reachable from Claude's cloud sandbox (see `docs/PROJECT_LOG.md`), so try them here
and let Claude know if either doesn't work as expected. The "default" source and Excel upload always work with no
network needed.

## Notes

- `venv\` should not be committed to any shared/version-controlled copy of this project (it's environment-specific and large) — it's already excluded by convention here; if you later add git, add a `.gitignore` with `venv/`.
- You don't need to touch the venv for read-only "watch along" purposes — every notebook Claude sends will already contain its executed outputs; you can just open and read it. The venv is only needed if you want to re-run cells or edit code yourself.
