"""Sunshine OS Developer Kit - Installer (Tkinter). Build: see README.MD"""
import base64, json, os, subprocess, sys, threading, datetime, tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path

BASE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
FILES = BASE / ".Files"
SETUP = FILES / "Setup Files"
DATA = Path(os.environ.get("PROGRAMDATA", ".")) / "SunshineDevKit"
STATE = DATA / "trial.json"
EMU_EXE = SETUP / "Emulator.exe"
WSL_BAT = SETUP / "silent_wsl_cubic.bat"
UNINSTALL = DATA / "uninstall_emulator.cmd"   # creato da install_emulator()
TASK = "SunshineDevKitTrialCheck"

# ---------- credenziali (file cifrato con password) ----------
def load_credentials():
    raw = (FILES / "Credentials.env").read_bytes()
    if raw.startswith(b"gAAAA"):                      # cifrato (Fernet)
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        for _ in range(3):
            pw = simpledialog.askstring("Password", "Password di Credentials.env:", show="*")
            if pw is None:
                break
            kdf = PBKDF2HMAC(hashes.SHA256(), 32, b"sunshine-devkit", 480000)
            key = base64.urlsafe_b64encode(kdf.derive(pw.encode()))
            try:
                raw = Fernet(key).decrypt(raw); break
            except InvalidToken:
                messagebox.showerror("Errore", "Password errata")
        else:
            raise SystemExit
        if raw.startswith(b"gAAAA"):
            raise SystemExit
    cfg = {}
    for line in raw.decode().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1); cfg[k.strip()] = v.strip()
    return cfg

# ---------- prova ----------
def trial_days_left(total):
    DATA.mkdir(parents=True, exist_ok=True)
    if not STATE.exists():
        STATE.write_text(json.dumps({"start": datetime.date.today().isoformat()}))
    start = datetime.date.fromisoformat(json.loads(STATE.read_text())["start"])
    return total - (datetime.date.today() - start).days

def expire():
    """Disinstalla l'emulatore e blocca nuove esecuzioni."""
    if UNINSTALL.exists():
        subprocess.run(["cmd", "/c", str(UNINSTALL)], creationflags=0x08000000)
    (DATA / "expired").write_text("1")
    subprocess.run(["schtasks", "/Delete", "/TN", TASK, "/F"], capture_output=True)

def is_expired():
    return (DATA / "expired").exists()

def check_mode():                       # Install.exe --check (task giornaliero)
    days = int(load_env_days())
    if is_expired() or trial_days_left(days) <= 0:
        expire()

def load_env_days():
    # in modalità --check non c'è GUI: salva i giorni nello state all'installazione
    return json.loads(STATE.read_text()).get("total", 3) if STATE.exists() else 3

# ---------- installazione ----------
def install_emulator(log):
    subprocess.run([str(EMU_EXE), "/S"], check=True)   # adatta il flag silenzioso
    DATA.mkdir(parents=True, exist_ok=True)
    # adatta il percorso: comando che disinstalla l'emulatore
    UNINSTALL.write_text('@echo off\r\n"%ProgramFiles%\\SunshineEmulator\\uninstall.exe" /S\r\n')
    subprocess.run(["schtasks", "/Create", "/TN", TASK, "/SC", "DAILY", "/F",
                    "/TR", f'"{Path(sys.executable)}" --check'], capture_output=True)

def install_cubic(log):
    subprocess.run(["cmd", "/c", str(WSL_BAT), str(FILES / "ISOs")], check=True)

# ---------- GUI ----------
class App(tk.Tk):
    def __init__(self, cfg):
        super().__init__()
        self.title("Sunshine OS Developer Kit"); self.geometry("560x420"); self.resizable(False, False)
        self.cfg = cfg
        self.total = int(cfg.get("TrialDays", 3))
        STATE_DATA = json.loads(STATE.read_text()) if STATE.exists() else {}
        trial_days_left(self.total)
        d = json.loads(STATE.read_text()); d["total"] = self.total; STATE.write_text(json.dumps(d))
        self.left = trial_days_left(self.total)
        self.var_emu = tk.BooleanVar(value=True)
        self.var_cubic = tk.BooleanVar(value=False)
        self.var_run_emu = tk.BooleanVar(value=True)
        self.var_run_cubic = tk.BooleanVar(value=False)
        self.frame = None
        self.show(self.page_readme)

    def show(self, builder):
        if self.frame: self.frame.destroy()
        self.frame = tk.Frame(self); self.frame.pack(fill="both", expand=True, padx=12, pady=12)
        builder(self.frame)

    def buttons(self, f, back=None, nxt=None, close=True, left_text=None):
        bar = tk.Frame(f); bar.pack(side="bottom", fill="x")
        if left_text: tk.Label(bar, text=left_text).pack(side="left")
        if nxt: tk.Button(bar, text="Avanti", width=10, command=nxt).pack(side="right", padx=4)
        if back: tk.Button(bar, text="Indietro", width=10, command=back).pack(side="right", padx=4)
        if close: tk.Button(bar, text="Chiudi", width=10, command=self.destroy).pack(side="right", padx=4)

    # 1 - README (sfondo giallo)
    def page_readme(self, f):
        f.configure(bg="#fff3b0")
        tk.Label(f, text="Leggi il readme (.Files/README.MD)", font=("Segoe UI", 13, "bold"),
                 bg="#fff3b0").pack(anchor="w")
        t = tk.Text(f, wrap="word"); t.pack(fill="both", expand=True, pady=8)
        try: t.insert("1.0", (FILES / "README.MD").read_text(encoding="utf-8"))
        except OSError: t.insert("1.0", "README.MD non trovato.")
        t.config(state="disabled")
        bar = tk.Frame(f, bg="#fff3b0"); bar.pack(side="bottom", fill="x")
        tk.Label(bar, bg="#fff3b0", text=f"{self.cfg.get('Name','')} - {max(self.left,0)} giorni").pack(side="left")
        tk.Button(bar, text="Avanti", width=10, command=lambda: self.show(self.page_choose)).pack(side="right", padx=4)
        tk.Button(bar, text="Chiudi", width=10, command=self.destroy).pack(side="right", padx=4)

    # 2 - scelta componenti
    def page_choose(self, f):
        tk.Label(f, text="Installa Sunshine OS developer kit", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(f, text="Puoi installare anche Cubic").pack(anchor="w", pady=4)
        box = tk.LabelFrame(f); box.pack(fill="x", pady=8)
        tk.Checkbutton(box, text="Emulatore", variable=self.var_emu).pack(anchor="w")
        tk.Checkbutton(box, text="Cubic (WSL)", variable=self.var_cubic).pack(anchor="w")
        self.buttons(f, back=lambda: self.show(self.page_readme), nxt=self.start_install, close=False)

    def start_install(self):
        if not (self.var_emu.get() or self.var_cubic.get()):
            messagebox.showwarning("Attenzione", "Seleziona almeno un componente."); return
        if self.left <= 0 or is_expired():
            messagebox.showerror("Prova scaduta", "Il periodo di prova è terminato."); return
        self.show(self.page_install)

    # 3 - installazione
    def page_install(self, f):
        tk.Label(f, text="Installazione", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        jobs = []
        if self.var_emu.get(): jobs.append(("Emulatore", install_emulator))
        if self.var_cubic.get(): jobs.append(("Cubic (silenzioso, WSL)", install_cubic))
        bars = {}
        for name, _ in jobs:
            tk.Label(f, text=name).pack(anchor="w", pady=(10, 0))
            pb = ttk.Progressbar(f, mode="indeterminate", length=500); pb.pack(anchor="w"); pb.start(12)
            bars[name] = pb
        def work():
            errs = []
            for name, fn in jobs:
                try: fn(print)
                except Exception as e: errs.append(f"{name}: {e}")
                self.after(0, lambda n=name: (bars[n].stop(), bars[n].config(mode="determinate", value=100)))
            self.after(0, lambda: self.finish(errs))
        threading.Thread(target=work, daemon=True).start()

    def finish(self, errs):
        if errs: messagebox.showerror("Errori", "\n".join(errs))
        self.show(self.page_done)

    # 4 - completato
    def page_done(self, f):
        tk.Label(f, text="Completato!", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=8)
        if self.var_emu.get():
            tk.Checkbutton(f, text="Avvia emulatore", variable=self.var_run_emu).pack(anchor="w")
        if self.var_cubic.get():
            tk.Checkbutton(f, text="Avvia cubic", variable=self.var_run_cubic).pack(anchor="w")
        def close():
            if self.var_emu.get() and self.var_run_emu.get() and not is_expired():
                subprocess.Popen([str(EMU_EXE)])
            if self.var_cubic.get() and self.var_run_cubic.get():
                subprocess.Popen(["wsl", "-d", "Ubuntu", "--", "cubic"])
            self.destroy()
        tk.Button(f, text="Chiudi", width=10, command=close).pack(side="bottom", anchor="e")

if __name__ == "__main__":
    if "--check" in sys.argv:
        check_mode(); sys.exit()
    root = tk.Tk(); root.withdraw()
    cfg = load_credentials(); root.destroy()
    App(cfg).mainloop()
