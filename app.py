#!/usr/bin/env python3
"""MarkItDown 批次轉換工具 - 圖形化介面"""

import json
import sys
import threading
import queue
import urllib.parse
import urllib.request
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from markitdown import MarkItDown

# ── 狀態常量 ──────────────────────────────────────────────────────────────────

STATUS_PENDING = "pending"
STATUS_CONVERTING = "converting"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

STATUS_CONFIG: dict[str, tuple[str, str]] = {
    STATUS_PENDING: ("等待中", "#9ca3af"),
    STATUS_CONVERTING: ("轉換中...", "#d97706"),
    STATUS_DONE: ("✓ 完成", "#16a34a"),
    STATUS_ERROR: ("✗ 錯誤", "#dc2626"),
    STATUS_SKIPPED: ("— 略過", "#9ca3af"),
}

SUPPORTED_FILETYPES = [
    (
        "所有支援格式",
        "*.pdf *.pptx *.ppt *.docx *.doc *.xlsx *.xls "
        "*.csv *.json *.xml *.html *.htm *.txt "
        "*.jpg *.jpeg *.png *.gif *.bmp *.tiff *.webp *.epub *.zip",
    ),
    ("文件", "*.pdf *.docx *.doc *.pptx *.ppt *.xlsx *.xls *.epub"),
    ("圖片", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff *.webp"),
    ("網頁", "*.html *.htm"),
    ("文字/資料", "*.txt *.csv *.json *.xml"),
    ("壓縮檔", "*.zip"),
    ("所有檔案", "*.*"),
]

SETTINGS_FILE = Path(__file__).parent / "settings.json"

LLM_PLATFORMS = ["Ollama", "OpenAI", "OpenRouter", "Gemini"]

LLM_DEFAULT_MODELS: dict[str, list[str]] = {
    "Ollama": [],
    "OpenAI": ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-4o"],
    "OpenRouter": [
        "openai/gpt-5.5",
        "openai/gpt-5.4",
        "anthropic/claude-opus-4.7",
        "google/gemini-3.1-flash-lite",
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro",
        "x-ai/grok-4.3",
    ],
    "Gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3-flash",
    ],
}


# ── FileRow ────────────────────────────────────────────────────────────────────

class FileRow:
    """代表清單中一列待轉換本地檔案的 UI 元件"""

    def __init__(self, parent: ctk.CTkScrollableFrame, path: Path, on_remove):
        self.path = path
        self.url: str | None = None
        self.status = STATUS_PENDING

        self.frame = ctk.CTkFrame(parent, height=36, fg_color="transparent")
        self.frame.pack(fill="x", pady=1)
        self.frame.pack_propagate(False)
        self.frame.grid_columnconfigure(1, weight=1)

        self.name_label = ctk.CTkLabel(
            self.frame,
            text=path.name,
            anchor="w",
            width=200,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)

        self.path_label = ctk.CTkLabel(
            self.frame,
            text=str(path.parent),
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self.path_label.grid(row=0, column=1, sticky="ew", padx=4)

        self.status_label = ctk.CTkLabel(
            self.frame,
            text="等待中",
            anchor="w",
            width=160,
            text_color="#9ca3af",
            font=ctk.CTkFont(size=11),
        )
        self.status_label.grid(row=0, column=2, sticky="w", padx=4)

        self.remove_btn = ctk.CTkButton(
            self.frame,
            text="✕",
            width=28,
            height=24,
            fg_color="transparent",
            hover_color="#fee2e2",
            text_color="#ef4444",
            font=ctk.CTkFont(size=12),
            command=lambda: on_remove(self),
        )
        self.remove_btn.grid(row=0, column=3, padx=(4, 8))

    def set_status(self, status: str, detail: str = "") -> None:
        self.status = status
        text, color = STATUS_CONFIG.get(status, ("未知", "gray"))
        if detail and status == STATUS_ERROR:
            text = f"✗ {detail[:55]}"
        elif detail and status == STATUS_DONE:
            text = f"✓ {detail}"
        elif detail and status == STATUS_CONVERTING:
            text = detail[:55]
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.frame.destroy()


# ── URLRow ─────────────────────────────────────────────────────────────────────

class URLRow:
    """代表清單中一列待轉換 URL 的 UI 元件"""

    def __init__(self, parent: ctk.CTkScrollableFrame, url: str, on_remove):
        self.url = url
        self.path: Path | None = None
        self.status = STATUS_PENDING

        self.frame = ctk.CTkFrame(parent, height=36, fg_color="transparent")
        self.frame.pack(fill="x", pady=1)
        self.frame.pack_propagate(False)
        self.frame.grid_columnconfigure(1, weight=1)

        parsed = urllib.parse.urlparse(url)
        display_name = parsed.path.rstrip("/").rsplit("/", 1)[-1] or parsed.netloc or url
        display_name = display_name[:40]

        self.name_label = ctk.CTkLabel(
            self.frame,
            text=f"🌐 {display_name}",
            anchor="w",
            width=200,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)

        display_url = url if len(url) <= 70 else url[:67] + "..."
        self.path_label = ctk.CTkLabel(
            self.frame,
            text=display_url,
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self.path_label.grid(row=0, column=1, sticky="ew", padx=4)

        self.status_label = ctk.CTkLabel(
            self.frame,
            text="等待中",
            anchor="w",
            width=160,
            text_color="#9ca3af",
            font=ctk.CTkFont(size=11),
        )
        self.status_label.grid(row=0, column=2, sticky="w", padx=4)

        self.remove_btn = ctk.CTkButton(
            self.frame,
            text="✕",
            width=28,
            height=24,
            fg_color="transparent",
            hover_color="#fee2e2",
            text_color="#ef4444",
            font=ctk.CTkFont(size=12),
            command=lambda: on_remove(self),
        )
        self.remove_btn.grid(row=0, column=3, padx=(4, 8))

    def set_status(self, status: str, detail: str = "") -> None:
        self.status = status
        text, color = STATUS_CONFIG.get(status, ("未知", "gray"))
        if detail and status == STATUS_ERROR:
            text = f"✗ {detail[:55]}"
        elif detail and status == STATUS_DONE:
            text = f"✓ {detail}"
        elif detail and status == STATUS_CONVERTING:
            text = detail[:55]
        self.status_label.configure(text=text, text_color=color)

    def destroy(self) -> None:
        self.frame.destroy()


# ── URLInputDialog ─────────────────────────────────────────────────────────────

class URLInputDialog(ctk.CTkToplevel):
    """URL 輸入對話框"""

    def __init__(self, parent):
        super().__init__(parent)
        self.result: list[str] = []
        self.title("新增網址")
        self.geometry("580x210")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        ctk.CTkLabel(
            self,
            text="輸入網址（每行一個，需以 http:// 或 https:// 開頭）：",
            font=ctk.CTkFont(size=12),
        ).pack(pady=(16, 6), padx=20, anchor="w")

        self._entry = ctk.CTkTextbox(self, height=72, font=ctk.CTkFont(size=12))
        self._entry.pack(fill="x", padx=20)

        self._error_label = ctk.CTkLabel(
            self, text="", text_color="#dc2626", font=ctk.CTkFont(size=11)
        )
        self._error_label.pack(pady=(4, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=8)

        ctk.CTkButton(btn_frame, text="新增", width=90, command=self._confirm).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            btn_frame,
            text="取消",
            width=90,
            fg_color="#6b7280",
            hover_color="#4b5563",
            command=self.destroy,
        ).pack(side="left", padx=6)

        self._entry.focus_set()

    def _confirm(self) -> None:
        raw = self._entry.get("1.0", "end").strip()
        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        if not urls:
            self._error_label.configure(text="請輸入至少一個網址")
            return
        invalid = [u for u in urls if not (u.startswith("http://") or u.startswith("https://"))]
        if invalid:
            self._error_label.configure(
                text=f"格式不正確（需以 http:// 或 https:// 開頭）：{invalid[0][:50]}"
            )
            return
        self.result = urls
        self.destroy()


# ── ConflictDialog ─────────────────────────────────────────────────────────────

class ConflictDialog(ctk.CTkToplevel):
    """同名檔案衝突處理對話框"""

    def __init__(self, parent, output_path: Path):
        super().__init__(parent)
        self.result = "skip"
        self.title("檔案已存在")
        self.geometry("480x190")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        ctk.CTkLabel(
            self,
            text="輸出檔案已存在：",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(pady=(20, 4), padx=20)

        ctk.CTkLabel(
            self,
            text=str(output_path),
            text_color="gray",
            font=ctk.CTkFont(size=11),
            wraplength=440,
        ).pack(pady=(0, 16), padx=20)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=8)

        ctk.CTkButton(
            btn_frame,
            text="覆蓋",
            width=90,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=lambda: self._respond("overwrite"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="自動重命名",
            width=110,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=lambda: self._respond("rename"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="略過此檔",
            width=90,
            fg_color="#6b7280",
            hover_color="#4b5563",
            command=lambda: self._respond("skip"),
        ).pack(side="left", padx=5)

    def _respond(self, choice: str) -> None:
        self.result = choice
        self.destroy()


# ── LLMSettingsDialog ──────────────────────────────────────────────────────────

class LLMSettingsDialog(ctk.CTkToplevel):
    """LLM 設定對話框"""

    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.result: dict | None = None
        self._settings = dict(settings)
        self._model_combo: ctk.CTkComboBox | None = None
        self._api_key_entry: ctk.CTkEntry | None = None
        self._ollama_url_entry: ctk.CTkEntry | None = None

        self.title("LLM 設定")
        self.geometry("560x460")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build_ui()
        platform = self._settings.get("platform", LLM_PLATFORMS[0])
        if platform in LLM_PLATFORMS:
            self._platform_var.set(platform)
        self._enabled_var.set(self._settings.get("enabled", False))
        self._ocr_var.set(self._settings.get("enable_ocr", False))
        self._on_platform_change(self._platform_var.get())

    def _build_ui(self) -> None:
        pad = {"padx": 20}

        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(16, 4), **pad)

        self._enabled_var = ctk.BooleanVar()
        ctk.CTkCheckBox(
            top_row,
            text="啟用 LLM（用於圖片描述與 OCR）",
            variable=self._enabled_var,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        platform_row = ctk.CTkFrame(self, fg_color="transparent")
        platform_row.pack(fill="x", **pad, pady=4)
        ctk.CTkLabel(
            platform_row, text="LLM 平台：", width=90, anchor="w",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")
        self._platform_var = ctk.StringVar(value=LLM_PLATFORMS[0])
        ctk.CTkOptionMenu(
            platform_row,
            values=LLM_PLATFORMS,
            variable=self._platform_var,
            command=self._on_platform_change,
            width=160,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        self._fields_frame = ctk.CTkFrame(self, fg_color="#f1f5f9", corner_radius=8)
        self._fields_frame.pack(fill="x", padx=20, pady=8)

        self._ocr_var = ctk.BooleanVar()
        self._ocr_check = ctk.CTkCheckBox(
            self,
            text="啟用圖片 OCR（使用 LLM 辨識圖片文字）",
            variable=self._ocr_var,
            font=ctk.CTkFont(size=12),
        )
        self._ocr_check.pack(anchor="w", pady=4, **pad)

        self._status_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), wraplength=510, justify="left"
        )
        self._status_label.pack(pady=(2, 0), **pad, anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)
        ctk.CTkButton(btn_frame, text="儲存", width=90, command=self._save).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            btn_frame,
            text="取消",
            width=90,
            fg_color="#6b7280",
            hover_color="#4b5563",
            command=self.destroy,
        ).pack(side="left", padx=6)

    def _clear_fields(self) -> None:
        for w in self._fields_frame.winfo_children():
            w.destroy()
        self._model_combo = None
        self._api_key_entry = None
        self._ollama_url_entry = None

    def _make_row(self, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(
            row, text=label, width=90, anchor="w", font=ctk.CTkFont(size=12)
        ).pack(side="left")
        return row

    def _on_platform_change(self, platform: str) -> None:
        self._clear_fields()
        self._status_label.configure(text="")
        if platform == "Ollama":
            self._build_ollama_fields()
        else:
            self._build_key_model_fields(platform)

    def _build_ollama_fields(self) -> None:
        row = self._make_row("Base URL：")
        self._ollama_url_entry = ctk.CTkEntry(
            row, width=300,
            placeholder_text="http://localhost:11434",
            font=ctk.CTkFont(size=12),
        )
        self._ollama_url_entry.pack(side="left", padx=4)

        model_row = self._make_row("模型：")
        self._model_combo = ctk.CTkComboBox(
            model_row, width=300, values=[], state="normal",
            font=ctk.CTkFont(size=12),
        )
        self._model_combo.pack(side="left", padx=4)

        btn_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 10))
        ctk.CTkButton(
            btn_row,
            text="測試連線 & 獲取模型清單",
            width=210,
            height=30,
            fg_color="#0f766e",
            hover_color="#0d9488",
            font=ctk.CTkFont(size=12),
            command=self._ollama_test_and_fetch,
        ).pack(side="left")

        saved_url = self._settings.get("ollama_url", "")
        if saved_url:
            self._ollama_url_entry.insert(0, saved_url)
        saved_model = self._settings.get("ollama_model", "")
        if saved_model:
            self._model_combo.set(saved_model)

    def _build_key_model_fields(self, platform: str) -> None:
        key_row = self._make_row("API Key：")
        self._api_key_entry = ctk.CTkEntry(
            key_row, width=280, show="*",
            placeholder_text="貼上 API Key...",
            font=ctk.CTkFont(size=12),
        )
        self._api_key_entry.pack(side="left", padx=4)

        self._show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            key_row,
            text="顯示",
            variable=self._show_key_var,
            width=55,
            font=ctk.CTkFont(size=11),
            command=lambda: self._api_key_entry.configure(
                show="" if self._show_key_var.get() else "*"
            ),
        ).pack(side="left", padx=4)

        model_row = self._make_row("模型：")
        default_models = LLM_DEFAULT_MODELS.get(platform, [])
        self._model_combo = ctk.CTkComboBox(
            model_row,
            width=300,
            values=default_models,
            state="normal",
            font=ctk.CTkFont(size=12),
        )
        self._model_combo.pack(side="left", padx=4)

        ctk.CTkLabel(self._fields_frame, text="", height=8).pack()

        key_field = f"{platform.lower()}_api_key"
        model_field = f"{platform.lower()}_model"
        saved_key = self._settings.get(key_field, "")
        if saved_key:
            self._api_key_entry.insert(0, saved_key)
        saved_model = self._settings.get(model_field, "")
        if saved_model:
            self._model_combo.set(saved_model)
        elif default_models:
            self._model_combo.set(default_models[0])

    def _ollama_test_and_fetch(self) -> None:
        url = (
            self._ollama_url_entry.get().strip().rstrip("/")
            if self._ollama_url_entry else ""
        ) or "http://localhost:11434"
        self._status_label.configure(text="⏳ 連線測試中...", text_color="#d97706")
        self.update()

        def worker():
            try:
                req = urllib.request.Request(
                    f"{url}/api/tags",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                self.after(0, lambda: self._ollama_fetch_done(models, url))
            except Exception as e:
                err = str(e)
                self.after(
                    0,
                    lambda err=err: self._status_label.configure(
                        text=f"✗ 連線失敗：{err[:100]}", text_color="#dc2626"
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _ollama_fetch_done(self, models: list[str], url: str) -> None:
        if not self._model_combo:
            return
        if models:
            self._model_combo.configure(values=models)
            current = self._model_combo.get().strip()
            if current not in models:
                self._model_combo.set(models[0])
            self._status_label.configure(
                text=f"✓ 連線成功（{url}），共 {len(models)} 個模型",
                text_color="#16a34a",
            )
        else:
            self._model_combo.configure(values=[])
            self._status_label.configure(
                text="✓ 連線成功，但 Ollama 尚未安裝任何模型",
                text_color="#d97706",
            )

    def _save(self) -> None:
        platform = self._platform_var.get()
        enabled = self._enabled_var.get()
        new_settings = dict(self._settings)
        new_settings["enabled"] = enabled
        new_settings["platform"] = platform
        new_settings["enable_ocr"] = self._ocr_var.get()

        model = self._model_combo.get().strip() if self._model_combo else ""

        if platform == "Ollama":
            url = (
                self._ollama_url_entry.get().strip().rstrip("/")
                if self._ollama_url_entry else ""
            ) or "http://localhost:11434"
            if enabled and not model:
                self._status_label.configure(
                    text="⚠ 請先點「測試連線 & 獲取模型清單」或手動輸入模型名稱",
                    text_color="#dc2626",
                )
                return
            new_settings["ollama_url"] = url
            new_settings["ollama_model"] = model
        else:
            api_key = self._api_key_entry.get().strip() if self._api_key_entry else ""
            key_field = f"{platform.lower()}_api_key"
            model_field = f"{platform.lower()}_model"
            if enabled and not api_key:
                self._status_label.configure(
                    text="⚠ 請輸入 API Key", text_color="#dc2626"
                )
                return
            if enabled and not model:
                self._status_label.configure(
                    text="⚠ 請選擇或輸入模型名稱", text_color="#dc2626"
                )
                return
            new_settings[key_field] = api_key
            new_settings[model_field] = model

        self.result = new_settings
        self.destroy()


# ── MarkItDownApp ──────────────────────────────────────────────────────────────

class MarkItDownApp(ctk.CTk):
    """MarkItDown 批次轉換工具主視窗"""

    APP_TITLE = "MarkItDown 批次轉換工具"

    def __init__(self):
        super().__init__()
        self.title(self.APP_TITLE)
        self.geometry("980x660")
        self.minsize(720, 500)

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._file_rows: list[FileRow | URLRow] = []
        self._output_dir: Path | None = None
        self._converting = False
        self._stop_event = threading.Event()
        self._conflict_queue: queue.Queue = queue.Queue()
        self._conflict_response_queue: queue.Queue = queue.Queue()
        self._llm_settings: dict = self._load_settings()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Settings ─────────────────────────────────────────────────────────────

    def _load_settings(self) -> dict:
        try:
            if SETTINGS_FILE.exists():
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_settings(self) -> None:
        try:
            SETTINGS_FILE.write_text(
                json.dumps(self._llm_settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── LLM client builder ───────────────────────────────────────────────────

    def _build_llm_client(self):
        """回傳 (client, model, enable_ocr)；未啟用或設定不完整時回傳 (None, None, False)"""
        if not self._llm_settings.get("enabled"):
            return None, None, False
        try:
            from openai import OpenAI
        except ImportError:
            return None, None, False

        platform = self._llm_settings.get("platform", "")
        enable_ocr = bool(self._llm_settings.get("enable_ocr", False))

        try:
            if platform == "Ollama":
                base_url = (
                    self._llm_settings.get("ollama_url", "http://localhost:11434")
                    .rstrip("/") + "/v1"
                )
                model = self._llm_settings.get("ollama_model", "").strip()
                if not model:
                    return None, None, False
                client = OpenAI(base_url=base_url, api_key="ollama")

            elif platform == "OpenAI":
                api_key = self._llm_settings.get("openai_api_key", "").strip()
                model = self._llm_settings.get("openai_model", "").strip()
                if not api_key or not model:
                    return None, None, False
                client = OpenAI(api_key=api_key)

            elif platform == "OpenRouter":
                api_key = self._llm_settings.get("openrouter_api_key", "").strip()
                model = self._llm_settings.get("openrouter_model", "").strip()
                if not api_key or not model:
                    return None, None, False
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                )

            elif platform == "Gemini":
                api_key = self._llm_settings.get("gemini_api_key", "").strip()
                model = self._llm_settings.get("gemini_model", "").strip()
                if not api_key or not model:
                    return None, None, False
                client = OpenAI(
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    api_key=api_key,
                )

            else:
                return None, None, False

            return client, model, enable_ocr

        except Exception:
            return None, None, False

    # ── UI 建構 ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_toolbar()
        self._build_file_list()
        self._build_bottom_bar()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#1d4ed8")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="  MarkItDown 批次轉換工具",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=16, pady=14)

        ctk.CTkLabel(
            header,
            text="Powered by Microsoft MarkItDown",
            font=ctk.CTkFont(size=11),
            text_color="#93c5fd",
        ).pack(side="right", padx=16)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))
        toolbar.grid_propagate(False)

        ctk.CTkButton(
            toolbar,
            text="＋ 新增檔案",
            command=self._add_files,
            width=115,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(0, 4), pady=8)

        ctk.CTkButton(
            toolbar,
            text="🌐 新增網址",
            command=self._add_urls,
            width=115,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0f766e",
            hover_color="#0d9488",
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            toolbar,
            text="清除已完成",
            command=self._clear_done,
            width=100,
            height=34,
            fg_color="#6b7280",
            hover_color="#4b5563",
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            toolbar,
            text="全部清除",
            command=self._clear_all,
            width=90,
            height=34,
            fg_color="#9ca3af",
            hover_color="#6b7280",
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkFrame(toolbar, width=1, height=30, fg_color="#d1d5db").pack(
            side="left", padx=12, pady=10
        )

        ctk.CTkLabel(toolbar, text="輸出目錄：", font=ctk.CTkFont(size=12)).pack(
            side="left"
        )

        self._output_dir_label = ctk.CTkLabel(
            toolbar,
            text="與原始檔案相同目錄",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self._output_dir_label.pack(side="left", padx=6)

        ctk.CTkButton(
            toolbar,
            text="選擇目錄",
            command=self._choose_output_dir,
            width=80,
            height=34,
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            toolbar,
            text="重置",
            command=self._reset_output_dir,
            width=55,
            height=34,
            fg_color="#9ca3af",
            hover_color="#6b7280",
        ).pack(side="left", padx=2, pady=8)

        self._llm_btn = ctk.CTkButton(
            toolbar,
            text="⚙ LLM",
            command=self._open_llm_settings,
            width=110,
            height=34,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self._llm_btn.pack(side="right", padx=(4, 0), pady=8)
        self._update_llm_btn()

    def _update_llm_btn(self) -> None:
        if self._llm_settings.get("enabled"):
            platform = self._llm_settings.get("platform", "LLM")
            self._llm_btn.configure(
                text=f"⚙ {platform} ✓",
                fg_color="#16a34a",
                hover_color="#15803d",
            )
        else:
            self._llm_btn.configure(
                text="⚙ LLM",
                fg_color="#6b7280",
                hover_color="#4b5563",
            )

    def _build_file_list(self) -> None:
        container = ctk.CTkFrame(self)
        container.grid(row=2, column=0, sticky="nsew", padx=12, pady=8)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            container, fg_color="#f1f5f9", height=30, corner_radius=6
        )
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="檔案名稱 / 網址",
            anchor="w",
            width=200,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#374151",
        ).grid(row=0, column=0, sticky="w", padx=(12, 4), pady=5)

        ctk.CTkLabel(
            header,
            text="原始路徑 / 完整網址",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#374151",
        ).grid(row=0, column=1, sticky="w", padx=4)

        ctk.CTkLabel(
            header,
            text="狀態",
            anchor="w",
            width=160,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#374151",
        ).grid(row=0, column=2, sticky="w", padx=4)

        ctk.CTkLabel(header, text="", width=40).grid(row=0, column=3)

        self._scrollable = ctk.CTkScrollableFrame(container, fg_color="transparent")
        self._scrollable.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._scrollable.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._scrollable,
            text="尚未新增任何檔案或網址\n請點選「＋ 新增檔案」或「🌐 新增網址」",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=13),
        )
        self._empty_label.pack(pady=60)

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=58, corner_radius=0, fg_color="#f8fafc")
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=14)

        self._progress_bar = ctk.CTkProgressBar(
            left, width=360, height=10, corner_radius=5
        )
        self._progress_bar.pack(side="left", pady=24)
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(
            left,
            text="",
            width=120,
            font=ctk.CTkFont(size=11),
            text_color="#6b7280",
        )
        self._progress_label.pack(side="left", padx=10)

        self._convert_btn = ctk.CTkButton(
            bar,
            text="▶  開始轉換",
            command=self._start_convert,
            width=140,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1d4ed8",
            hover_color="#1e40af",
        )
        self._convert_btn.grid(row=0, column=1, padx=14, pady=9)

    # ── LLM 設定 ──────────────────────────────────────────────────────────────

    def _open_llm_settings(self) -> None:
        dialog = LLMSettingsDialog(self, self._llm_settings)
        self.wait_window(dialog)
        if dialog.result is not None:
            self._llm_settings = dialog.result
            self._save_settings()
            self._update_llm_btn()

    # ── 檔案管理 ──────────────────────────────────────────────────────────────

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="選擇要轉換的檔案", filetypes=SUPPORTED_FILETYPES
        )
        if not paths:
            return
        if self._empty_label.winfo_ismapped():
            self._empty_label.pack_forget()
        for p in paths:
            p_path = Path(p).resolve()
            if not any(isinstance(r, FileRow) and r.path == p_path for r in self._file_rows):
                row = FileRow(self._scrollable, p_path, self._remove_file_row)
                self._file_rows.append(row)

    def _add_urls(self) -> None:
        dialog = URLInputDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        if self._empty_label.winfo_ismapped():
            self._empty_label.pack_forget()
        for url in dialog.result:
            if not any(isinstance(r, URLRow) and r.url == url for r in self._file_rows):
                row = URLRow(self._scrollable, url, self._remove_file_row)
                self._file_rows.append(row)

    def _remove_file_row(self, row: "FileRow | URLRow") -> None:
        if self._converting:
            return
        row.destroy()
        self._file_rows.remove(row)
        if not self._file_rows:
            self._empty_label.pack(pady=60)

    def _clear_done(self) -> None:
        done_statuses = {STATUS_DONE, STATUS_SKIPPED}
        to_remove = [r for r in self._file_rows if r.status in done_statuses]
        for r in to_remove:
            r.destroy()
            self._file_rows.remove(r)
        if not self._file_rows:
            self._empty_label.pack(pady=60)

    def _clear_all(self) -> None:
        if self._converting:
            return
        for r in self._file_rows:
            r.destroy()
        self._file_rows.clear()
        self._progress_bar.set(0)
        self._progress_label.configure(text="")
        self._empty_label.pack(pady=60)

    def _choose_output_dir(self) -> None:
        d = filedialog.askdirectory(title="選擇輸出目錄")
        if d:
            self._output_dir = Path(d).resolve()
            display = str(self._output_dir)
            if len(display) > 65:
                display = "..." + display[-62:]
            self._output_dir_label.configure(text=display, text_color="#1d4ed8")

    def _reset_output_dir(self) -> None:
        self._output_dir = None
        self._output_dir_label.configure(
            text="與原始檔案相同目錄", text_color="gray"
        )

    # ── 轉換邏輯 ──────────────────────────────────────────────────────────────

    def _start_convert(self) -> None:
        pending = [r for r in self._file_rows if r.status != STATUS_DONE]
        if not pending:
            messagebox.showinfo("提示", "目前沒有待轉換的檔案。")
            return

        self._converting = True
        self._stop_event.clear()
        self._convert_btn.configure(state="disabled", text="轉換中...")
        self._progress_bar.set(0)
        self._progress_label.configure(text=f"0 / {len(pending)}")

        threading.Thread(
            target=self._convert_worker, args=(pending,), daemon=True
        ).start()
        self.after(100, self._poll_conflict_queue)

    def _poll_conflict_queue(self) -> None:
        try:
            conflict_info = self._conflict_queue.get_nowait()
            self._handle_conflict(conflict_info)
        except queue.Empty:
            pass
        if self._converting:
            self.after(100, self._poll_conflict_queue)

    def _handle_conflict(self, conflict_info: dict) -> None:
        dialog = ConflictDialog(self, conflict_info["output_path"])
        self.wait_window(dialog)
        self._conflict_response_queue.put(dialog.result)

    def _resolve_output_path(self, stem: str, out_dir: Path) -> "Path | str | None":
        output_path = out_dir / (stem + ".md")
        if not output_path.exists():
            return output_path

        self._conflict_queue.put({"output_path": output_path})

        choice = None
        while not self._stop_event.is_set():
            try:
                choice = self._conflict_response_queue.get(timeout=0.5)
                break
            except queue.Empty:
                continue

        if self._stop_event.is_set() or choice is None:
            return "stop"
        if choice == "skip":
            return None
        elif choice == "rename":
            counter = 1
            while output_path.exists():
                output_path = out_dir / f"{stem}_{counter}.md"
                counter += 1
            return output_path
        else:
            return output_path

    def _convert_worker(self, rows: list) -> None:
        llm_client, llm_model, enable_ocr = self._build_llm_client()

        if llm_client and llm_model:
            md = MarkItDown(
                llm_client=llm_client,
                llm_model=llm_model,
                enable_plugins=enable_ocr,
            )
        else:
            md = MarkItDown()

        total = len(rows)

        for idx, row in enumerate(rows):
            if self._stop_event.is_set():
                break

            self.after(0, lambda r=row: r.set_status(STATUS_CONVERTING))
            output_path: Path | None = None

            try:
                if isinstance(row, URLRow):
                    out_dir = (self._output_dir or Path.cwd()).resolve()
                    parsed = urllib.parse.urlparse(row.url)
                    stem = (
                        parsed.path.rstrip("/").rsplit("/", 1)[-1]
                        or parsed.netloc or "url_output"
                    )
                    stem = "".join(
                        c if c.isalnum() or c in "-_." else "_" for c in stem
                    )[:80] or "url_output"
                else:
                    out_dir = (self._output_dir or row.path.parent).resolve()
                    stem = row.path.stem

                out_dir.mkdir(parents=True, exist_ok=True)

                resolved = self._resolve_output_path(stem, out_dir)
                if resolved == "stop":
                    break
                if resolved is None:
                    self.after(0, lambda r=row: r.set_status(STATUS_SKIPPED))
                    self.after(0, lambda i=idx + 1, t=total: self._update_progress(i, t))
                    continue

                output_path = resolved

                if isinstance(row, URLRow):
                    result = md.convert(row.url)
                else:
                    result = md.convert_local(str(row.path))

                output_path.write_text(result.text_content, encoding="utf-8")
                self.after(
                    0,
                    lambda r=row, p=output_path.name: r.set_status(STATUS_DONE, p),
                )

            except Exception as ex:
                err_msg = str(ex)
                llm_error_keywords = (
                    "model", "api", "connection", "auth", "404", "401",
                    "rate", "timeout", "llm", "openai", "vision",
                )
                is_llm_error = llm_client and any(
                    kw in err_msg.lower() for kw in llm_error_keywords
                )
                if is_llm_error and output_path is not None:
                    try:
                        self.after(
                            0,
                            lambda r=row: r.set_status(
                                STATUS_CONVERTING, "⚠ LLM 失敗，降級轉換中..."
                            ),
                        )
                        md_plain = MarkItDown()
                        if isinstance(row, URLRow):
                            result = md_plain.convert(row.url)
                        else:
                            result = md_plain.convert_local(str(row.path))
                        output_path.write_text(result.text_content, encoding="utf-8")
                        self.after(
                            0,
                            lambda r=row, p=output_path.name: r.set_status(
                                STATUS_DONE, f"⚠LLM降級 · {p}"
                            ),
                        )
                    except Exception as ex2:
                        self.after(
                            0,
                            lambda r=row, e=str(ex2): r.set_status(STATUS_ERROR, e),
                        )
                else:
                    self.after(
                        0,
                        lambda r=row, e=err_msg: r.set_status(STATUS_ERROR, e),
                    )

            self.after(
                0, lambda i=idx + 1, t=total: self._update_progress(i, t)
            )

        self.after(0, self._on_convert_done)

    def _update_progress(self, current: int, total: int) -> None:
        self._progress_bar.set(current / total)
        self._progress_label.configure(text=f"{current} / {total}")

    def _on_convert_done(self) -> None:
        self._converting = False
        self._convert_btn.configure(state="normal", text="▶  開始轉換")

        done = sum(1 for r in self._file_rows if r.status == STATUS_DONE)
        error = sum(1 for r in self._file_rows if r.status == STATUS_ERROR)
        skipped = sum(1 for r in self._file_rows if r.status == STATUS_SKIPPED)

        lines = [f"✓ 成功：{done} 個"]
        if error:
            lines.append(f"✗ 失敗：{error} 個")
        if skipped:
            lines.append(f"— 略過：{skipped} 個")
        messagebox.showinfo("轉換完成", "\n".join(lines))

    def _on_close(self) -> None:
        self._stop_event.set()
        try:
            self._conflict_response_queue.put_nowait("skip")
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = MarkItDownApp()
    app.mainloop()
