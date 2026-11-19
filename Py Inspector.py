import tkinter as tk
from tkinter import filedialog, messagebox
import ast
import json
import os
import subprocess

HOME_DIR = os.path.expanduser("~")
DEFAULT_SAVE_DIR = os.path.join(HOME_DIR, "HammerDeskSaves")
CFG_DIR = os.path.join(HOME_DIR, ".hammer_desk_cfg")
CFG_PATH = os.path.join(CFG_DIR, "config.json")

# Hammer Editor (Source / HL2) paleta boja
H_BG = "#2b2f36"
H_PANEL = "#353a42"
H_BAR = "#23272d"
H_INPUT = "#171a1f"
H_BORDER = "#4c535e"
H_FG = "#e6e9ef"
H_MUTED = "#9aa2b1"
H_ORANGE = "#e8831d"
H_ENTITY = "#38b6ff"
H_WARN = "#f0b429"
H_OK = "#4cc38a"
H_ERR = "#ff5c5c"


class PyInspectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Py Inspector")
        self.root.geometry("1120x700")
        self.root.minsize(860, 520)
        self.root.configure(bg=H_BG)

        self.save_dir = self.load_save_dir()
        self.ensure_dir(self.save_dir)

        self.current_file = ""
        self.items = self.load_items()
        self.selected_idx = None
        self.scan_job = None

        self.build_ui()
        self.refresh_all()
        self.scan_code_for_errors(manual=False)

    def ensure_dir(self, path):
        if path:
            os.makedirs(path, exist_ok=True)

    def load_save_dir(self):
        if os.path.isfile(CFG_PATH):
            try:
                with open(CFG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    folder = cfg.get("save_dir", "")
                    if isinstance(folder, str) and folder.strip():
                        return folder.strip()
            except Exception:
                pass
        return DEFAULT_SAVE_DIR

    def save_save_dir(self, folder):
        try:
            self.ensure_dir(CFG_DIR)
            with open(CFG_PATH, "w", encoding="utf-8") as f:
                json.dump({"save_dir": folder}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def items_file(self):
        return os.path.join(self.save_dir, "entities_manifest.json")

    def load_items(self):
        p = self.items_file()
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [x for x in data if isinstance(x, dict) and "path" in x]
            except Exception:
                pass
        return []

    def save_items(self):
        self.ensure_dir(self.save_dir)
        try:
            with open(self.items_file(), "w", encoding="utf-8") as f:
                json.dump(self.items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Greska", f"Ne mogu spremiti listu:\n{e}")

    def make_btn(self, parent, text, cmd, bg=H_PANEL, fg=H_FG):
        return tk.Button(
            parent, text=text, command=cmd,
            font=("Tahoma", 8, "bold"),
            bg=bg, fg=fg, activebackground=H_BORDER, activeforeground="#ffffff",
            relief=tk.RAISED, bd=1, padx=9, pady=3, cursor="hand2"
        )

    def build_ui(self):
        # Gornji toolbar
        toolbar = tk.Frame(self.root, bg=H_BAR, padx=6, pady=5, highlightbackground=H_BORDER, highlightthickness=1)
        toolbar.pack(fill=tk.X)

        tk.Label(toolbar, text="PY INSPECTOR", font=("Tahoma", 9, "bold"), bg=H_BAR, fg=H_ORANGE).pack(side=tk.LEFT, padx=(2, 10))

        self.make_btn(toolbar, "New", self.new_buffer).pack(side=tk.LEFT, padx=(0, 3))
        self.make_btn(toolbar, "Open", self.open_file).pack(side=tk.LEFT, padx=(0, 3))
        self.make_btn(toolbar, "Save", self.save_file, bg="#2f5d3a", fg="#ffffff").pack(side=tk.LEFT, padx=(0, 3))
        self.make_btn(toolbar, "Save As", self.save_file_as).pack(side=tk.LEFT, padx=(0, 10))

        self.make_btn(toolbar, "Set Save Folder", self.pick_save_folder, bg=H_PANEL, fg=H_ORANGE).pack(side=tk.LEFT, padx=(0, 3))
        self.make_btn(toolbar, "Open Folder", self.open_save_folder).pack(side=tk.LEFT, padx=(0, 10))

        self.make_btn(toolbar, "Run JSON in Py", self.run_editor_json_in_py, bg=H_ORANGE, fg="#141619").pack(side=tk.LEFT, padx=(0, 3))
        self.make_btn(toolbar, "Scan Now", lambda: self.scan_code_for_errors(manual=True), bg="#27496d", fg="#ffffff").pack(side=tk.LEFT)

        self.doc_lbl = tk.Label(toolbar, text="[unnamed.py]", font=("Consolas", 9), bg=H_BAR, fg=H_MUTED)
        self.doc_lbl.pack(side=tk.RIGHT, padx=8)

        # Glavni radni prostor (lijevo entiteti/skripte, desno editor + CMD error scanner bar)
        main = tk.Frame(self.root, bg=H_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Lijevi stupac: Entities / Scripts
        left = tk.Frame(main, bg=H_PANEL, width=230, highlightbackground=H_BORDER, highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(
            left, text="ENTITIES / SCRIPTS", font=("Tahoma", 8, "bold"),
            bg=H_BAR, fg=H_ORANGE, anchor="w", padx=8, pady=4
        ).pack(fill=tk.X)

        self.entity_list = tk.Listbox(
            left, bg=H_INPUT, fg=H_FG, selectbackground=H_BORDER,
            selectforeground="#ffffff", font=("Consolas", 9),
            bd=0, highlightthickness=0, activestyle="none"
        )
        self.entity_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.entity_list.bind("<<ListboxSelect>>", self.on_list_select)
        self.entity_list.bind("<Double-Button-1>", lambda e: self.run_selected_entity())

        ent_btns = tk.Frame(left, bg=H_PANEL, padx=6, pady=6)
        ent_btns.pack(fill=tk.X)
        self.make_btn(ent_btns, "Run", self.run_selected_entity, bg="#2f5d3a", fg="#ffffff").pack(side=tk.LEFT)
        self.make_btn(ent_btns, "+ Add", self.add_entity).pack(side=tk.LEFT, padx=(4, 0))
        self.make_btn(ent_btns, "Del", self.delete_entity, bg="#6e2929", fg="#ffffff").pack(side=tk.RIGHT)

        # Desni stupac: Editor gore + CMD Error Scanner bar dolje
        right = tk.Frame(main, bg=H_BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        editor_panel = tk.Frame(right, bg=H_PANEL, highlightbackground=H_BORDER, highlightthickness=1)
        editor_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        prop_hdr = tk.Frame(editor_panel, bg=H_BAR, padx=8, pady=4)
        prop_hdr.pack(fill=tk.X)
        tk.Label(prop_hdr, text="OBJECT PROPERTIES / SOURCE", font=("Tahoma", 8, "bold"), bg=H_BAR, fg=H_FG).pack(side=tk.LEFT)
        self.meta_lbl = tk.Label(prop_hdr, text="Ln 1, Col 1", font=("Consolas", 8), bg=H_BAR, fg=H_MUTED)
        self.meta_lbl.pack(side=tk.RIGHT)

        self.editor = tk.Text(
            editor_panel, bg=H_INPUT, fg=H_FG, insertbackground=H_ORANGE,
            font=("Consolas", 10), relief=tk.FLAT, padx=10, pady=8, undo=True
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.editor.bind("<KeyRelease>", self.on_editor_change)
        self.editor.bind("<ButtonRelease-1>", lambda e: self.update_cursor_info())
        self.editor.bind("<<Paste>>", lambda e: self.root.after(30, lambda: self.scan_code_for_errors(manual=False)))

        # CMD Error Scanner Bar
        cmd_panel = tk.Frame(right, bg=H_PANEL, height=185, highlightbackground=H_BORDER, highlightthickness=1)
        cmd_panel.pack(fill=tk.X, side=tk.BOTTOM)
        cmd_panel.pack_propagate(False)

        cmd_hdr = tk.Frame(cmd_panel, bg=H_BAR, padx=8, pady=4)
        cmd_hdr.pack(fill=tk.X)

        tk.Label(cmd_hdr, text="CMD // PY & JSON ERROR SCANNER", font=("Consolas", 8, "bold"), bg=H_BAR, fg=H_ORANGE).pack(side=tk.LEFT)
        self.scan_badge = tk.Label(cmd_hdr, text="SCAN: OK", font=("Consolas", 8, "bold"), bg=H_BAR, fg=H_OK)
        self.scan_badge.pack(side=tk.LEFT, padx=(12, 0))

        self.make_btn(cmd_hdr, "Clear CMD", self.clear_cmd, bg=H_PANEL, fg=H_MUTED).pack(side=tk.RIGHT)

        self.cmd_box = tk.Text(
            cmd_panel, bg="#101216", fg=H_FG, font=("Consolas", 9),
            relief=tk.FLAT, padx=8, pady=6, state=tk.DISABLED, wrap=tk.WORD
        )
        self.cmd_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 2))
        self.cmd_box.tag_configure("err", foreground=H_ERR)
        self.cmd_box.tag_configure("warn", foreground=H_WARN)
        self.cmd_box.tag_configure("ok", foreground=H_OK)
        self.cmd_box.tag_configure("dim", foreground=H_MUTED)

        cmd_in_bar = tk.Frame(cmd_panel, bg=H_BAR, padx=6, pady=3)
        cmd_in_bar.pack(fill=tk.X)
        tk.Label(cmd_in_bar, text="CMD>", font=("Consolas", 9, "bold"), bg=H_BAR, fg=H_ENTITY).pack(side=tk.LEFT)

        self.cmd_entry = tk.Entry(
            cmd_in_bar, bg=H_INPUT, fg=H_FG, insertbackground=H_ORANGE,
            font=("Consolas", 9), relief=tk.FLAT
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=2)
        self.cmd_entry.bind("<Return>", self.run_cmd_line)

        # Donja status traka
        bottom = tk.Frame(self.root, bg=H_BAR, padx=8, pady=4, highlightbackground=H_BORDER, highlightthickness=1)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        self.console_lbl = tk.Label(bottom, text="Py Inspector ready.", font=("Consolas", 8), bg=H_BAR, fg=H_MUTED)
        self.console_lbl.pack(side=tk.LEFT)

        self.dir_lbl = tk.Label(bottom, text="", font=("Consolas", 8), bg=H_BAR, fg=H_ORANGE)
        self.dir_lbl.pack(side=tk.RIGHT)

    def log(self, text, color=H_MUTED):
        self.console_lbl.config(text=text, fg=color)

    def cmd_write(self, text, tag="dim"):
        self.cmd_box.config(state=tk.NORMAL)
        self.cmd_box.insert(tk.END, text + "\n", tag)
        self.cmd_box.see(tk.END)
        self.cmd_box.config(state=tk.DISABLED)

    def clear_cmd(self):
        self.cmd_box.config(state=tk.NORMAL)
        self.cmd_box.delete("1.0", tk.END)
        self.cmd_box.config(state=tk.DISABLED)

    def update_cursor_info(self):
        idx = self.editor.index(tk.INSERT)
        line, col = idx.split(".")
        self.meta_lbl.config(text=f"Ln {line}, Col {int(col) + 1}")

    def on_editor_change(self, event=None):
        self.update_cursor_info()
        if self.scan_job is not None:
            try:
                self.root.after_cancel(self.scan_job)
            except Exception:
                pass
        self.scan_job = self.root.after(250, lambda: self.scan_code_for_errors(manual=False))

    def detect_mode(self, content):
        ext = os.path.splitext(self.current_file or "")[1].lower()
        if ext == ".json":
            return "json"
        if ext == ".py":
            return "python"
        stripped = content.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"
        return "python"

    def scan_code_for_errors(self, manual=True):
        self.scan_job = None
        content = self.editor.get("1.0", "end-1c")

        if manual:
            self.clear_cmd()

        if not content.strip():
            self.scan_badge.config(text="SCAN: EMPTY", fg=H_MUTED)
            if manual:
                self.cmd_write("[SCAN] Buffer je prazan.", "dim")
            return

        mode = self.detect_mode(content)
        errors = []
        warnings = []

        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "\t" in line and line.lstrip() != line and " " in line[: len(line) - len(line.lstrip())]:
                warnings.append(f"Line {idx}: pomijesani tabovi i razmaci u uvlacenju.")
            if line.rstrip() != line and len(line) - len(line.rstrip()) > 4:
                warnings.append(f"Line {idx}: suvisni razmaci na kraju linije.")

        if mode == "json":
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                errors.append(f"JSON Error (Ln {e.lineno}, Col {e.colno}): {e.msg}")
            except Exception as e:
                errors.append(f"JSON Error: {e}")
        else:
            try:
                compile(content, self.current_file or "<editor>", "exec")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        warnings.append(f"Line {node.lineno}: gol 'except:' blok bez tipa greske.")
            except SyntaxError as e:
                ln = e.lineno or 1
                col = (e.offset or 0) + 1
                errors.append(f"Python SyntaxError (Ln {ln}, Col {col}): {e.msg}")
            except Exception as e:
                errors.append(f"Python Error: {e}")

        if errors:
            self.scan_badge.config(text=f"SCAN: {len(errors)} ERR", fg=H_ERR)
            if manual:
                for err in errors:
                    self.cmd_write(f"[ERR] {err}", "err")
                for w in warnings:
                    self.cmd_write(f"[WARN] {w}", "warn")
            else:
                self.clear_cmd()
                for err in errors:
                    self.cmd_write(f"[ERR] {err}", "err")
                for w in warnings:
                    self.cmd_write(f"[WARN] {w}", "warn")
        elif warnings:
            self.scan_badge.config(text=f"SCAN: {len(warnings)} WARN", fg=H_WARN)
            if manual:
                self.cmd_write(f"[OK] {mode.upper()} sintaksa ispravna, ali ima upozorenja:", "warn")
                for w in warnings:
                    self.cmd_write(f"[WARN] {w}", "warn")
        else:
            self.scan_badge.config(text=f"SCAN: {mode.upper()} OK", fg=H_OK)
            if manual:
                self.cmd_write(f"[OK] Nema gresaka ({mode.upper()} provjera prosla).", "ok")

    def run_cmd_line(self, event=None):
        cmd = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, tk.END)
        if not cmd:
            return

        self.cmd_write(f"CMD> {cmd}", "dim")
        low = cmd.lower()
        if low in ("scan", "check"):
            self.scan_code_for_errors(manual=True)
            return
        if low == "clear":
            self.clear_cmd()
            return
        if low == "runjson":
            self.run_editor_json_in_py()
            return

        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=self.save_dir,
                capture_output=True, text=True, timeout=15
            )
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    self.cmd_write(line, "ok")
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    self.cmd_write(line, "err")
            if not proc.stdout and not proc.stderr:
                self.cmd_write(f"[EXIT {proc.returncode}]", "dim")
        except Exception as e:
            self.cmd_write(f"[CMD ERR] {e}", "err")

    def refresh_all(self):
        self.refresh_entity_list()
        self.dir_lbl.config(text=f"Save Dir: {self.save_dir}")
        self.update_cursor_info()

    def refresh_entity_list(self):
        self.entity_list.delete(0, tk.END)
        for i, item in enumerate(self.items):
            name = item.get("name") or os.path.basename(item.get("path", f"entity_{i}"))
            kind = os.path.splitext(item.get("path", ""))[1].lower() or ".item"
            self.entity_list.insert(tk.END, f"[{kind}] {name}")

    def on_list_select(self, event):
        sel = self.entity_list.curselection()
        if sel:
            self.selected_idx = sel[0]

    def pick_save_folder(self):
        chosen = filedialog.askdirectory(title="Odaberi mapu za spremanje", initialdir=self.save_dir)
        if chosen:
            self.ensure_dir(chosen)
            self.save_dir = chosen
            self.save_save_dir(chosen)
            self.items = self.load_items()
            self.selected_idx = None
            self.save_items()
            self.refresh_all()
            self.log(f"Save folder set to: {self.save_dir}", H_OK)

    def open_save_folder(self):
        self.ensure_dir(self.save_dir)
        try:
            os.startfile(self.save_dir)
        except Exception as e:
            messagebox.showerror("Greska", str(e))

    def add_entity(self):
        p = filedialog.askopenfilename(
            title="Dodaj program, .py skriptu ili .json",
            filetypes=[("Scripts, JSON & Exe", "*.py;*.json;*.exe;*.bat;*.cmd"), ("All files", "*.*")]
        )
        if p:
            name = os.path.splitext(os.path.basename(p))[0]
            self.items.append({"name": name, "path": p})
            self.selected_idx = len(self.items) - 1
            self.save_items()
            self.refresh_all()
            self.log(f"Added entity: {name}", H_OK)

    def delete_entity(self):
        if self.selected_idx is None or self.selected_idx >= len(self.items):
            return
        removed = self.items.pop(self.selected_idx)
        self.selected_idx = None
        self.save_items()
        self.refresh_all()
        self.log(f"Removed entity: {removed.get('name', '')}", H_WARN)

    def execute_json_in_python(self, json_path, raw_content=None):
        self.ensure_dir(self.save_dir)
        if raw_content is None:
            with open(json_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read()

        try:
            parsed = json.loads(raw_content)
        except Exception as e:
            self.cmd_write(f"[ERR] Neispravan JSON: {e}", "err")
            messagebox.showerror("JSON Error", f"Neispravan JSON:\n{e}")
            return

        runners_dir = os.path.join(self.save_dir, "_json_runners")
        self.ensure_dir(runners_dir)
        stem = os.path.splitext(os.path.basename(json_path or "edited"))[0]
        py_file = os.path.join(runners_dir, f"{stem}_py_run.py")

        if isinstance(parsed, dict):
            code_val = None
            for k in ("code", "script", "python", "py"):
                if isinstance(parsed.get(k), str) and parsed[k].strip():
                    code_val = parsed[k]
                    break
            if code_val is not None:
                py_src = code_val
            else:
                py_src = (
                    "import json\n\n"
                    f"data = {json.dumps(parsed, indent=4, ensure_ascii=False)}\n"
                    "print('Keys:', list(data.keys()))\n"
                    "print(json.dumps(data, indent=2, ensure_ascii=False))\n"
                    "input('Press Enter to exit...')\n"
                )
        else:
            py_src = (
                "import json\n\n"
                f"data = {json.dumps(parsed, indent=4, ensure_ascii=False)}\n"
                "print(json.dumps(data, indent=2, ensure_ascii=False))\n"
                "input('Press Enter to exit...')\n"
            )

        with open(py_file, "w", encoding="utf-8") as f:
            f.write(py_src)

        cwd = os.path.dirname(json_path) if (json_path and os.path.dirname(json_path)) else self.save_dir
        subprocess.Popen(["py", py_file], cwd=cwd)
        self.log(f"Running JSON via Python: {os.path.basename(py_file)}", H_OK)
        self.cmd_write(f"[RUN] Pokrenuto u Pythonu: {py_file}", "ok")

    def run_editor_json_in_py(self):
        raw = self.editor.get("1.0", "end-1c")
        if not raw.strip():
            messagebox.showwarning("Prazno", "Editor nema sadrzaja.")
            return

        target = self.current_file
        if not target or not target.lower().endswith(".json"):
            self.ensure_dir(self.save_dir)
            target = os.path.join(self.save_dir, "edited_map_script.json")
            with open(target, "w", encoding="utf-8") as f:
                f.write(raw)
            self.current_file = target
            self.doc_lbl.config(text=os.path.basename(target), fg=H_FG)

        self.execute_json_in_python(target, raw_content=raw)

    def run_selected_entity(self):
        if self.selected_idx is None or self.selected_idx >= len(self.items):
            return
        item = self.items[self.selected_idx]
        p = item.get("path", "")
        if not p or not os.path.isfile(p):
            messagebox.showwarning("Nema datoteke", f"Datoteka ne postoji:\n{p}")
            return
        try:
            cwd = os.path.dirname(p) or None
            if p.lower().endswith(".json"):
                self.execute_json_in_python(p)
            elif p.lower().endswith(".py"):
                subprocess.Popen(["py", p], cwd=cwd)
                self.log(f"Launched Python script: {os.path.basename(p)}", H_OK)
            else:
                subprocess.Popen([p], cwd=cwd)
                self.log(f"Launched: {os.path.basename(p)}", H_OK)
        except Exception as e:
            messagebox.showerror("Greska", str(e))

    def new_buffer(self):
        self.editor.delete("1.0", tk.END)
        self.current_file = ""
        self.doc_lbl.config(text="[unnamed.py]", fg=H_MUTED)
        self.update_cursor_info()
        self.scan_code_for_errors(manual=False)
        self.log("New buffer.", H_MUTED)

    def open_file(self):
        p = filedialog.askopenfilename(
            title="Otvori datoteku",
            initialdir=self.save_dir,
            filetypes=[("JSON, Python & Text", "*.json;*.py;*.txt;*.vmf;*.cfg"), ("All files", "*.*")]
        )
        if p:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    txt = f.read()
                self.current_file = p
                self.doc_lbl.config(text=os.path.basename(p), fg=H_FG)
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", txt)
                self.update_cursor_info()
                self.scan_code_for_errors(manual=True)
                self.log(f"Opened: {p}", H_ENTITY)
            except Exception as e:
                messagebox.showerror("Greska", str(e))

    def save_file(self):
        if self.current_file:
            try:
                self.ensure_dir(os.path.dirname(self.current_file))
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(self.editor.get("1.0", "end-1c"))
                self.log(f"Saved: {self.current_file}", H_OK)
            except Exception as e:
                messagebox.showerror("Greska", str(e))
        else:
            self.save_file_as()

    def save_file_as(self):
        self.ensure_dir(self.save_dir)
        init_name = os.path.basename(self.current_file) if self.current_file else "script.json"
        p = filedialog.asksaveasfilename(
            title="Spremi kao",
            initialdir=self.save_dir,
            initialfile=init_name,
            filetypes=[("JSON files", "*.json"), ("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if p:
            try:
                self.ensure_dir(os.path.dirname(p))
                with open(p, "w", encoding="utf-8") as f:
                    f.write(self.editor.get("1.0", "end-1c"))
                self.current_file = p
                self.doc_lbl.config(text=os.path.basename(p), fg=H_FG)
                self.log(f"Saved as: {p}", H_OK)
            except Exception as e:
                messagebox.showerror("Greska", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = PyInspectorApp(root)
    root.mainloop()