# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定檔
執行方式：pyinstaller app.spec
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# CustomTkinter：需要帶入主題/字型等資源檔
tmp = collect_all("customtkinter")
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

# MarkItDown 本體與所有轉換器
tmp = collect_all("markitdown")
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

# Magika：markitdown 用來偵測檔案類型，含 ML 模型資料
tmp = collect_all("magika")
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

# charset_normalizer：有預編譯 mypyc 模組，PyInstaller 不一定能自動偵測
hiddenimports += collect_submodules("charset_normalizer")

extra_hidden = [
    # PDF
    "pdfminer",
    "pdfminer.high_level",
    "pdfminer.layout",
    "pdfminer.pdfinterp",
    "pdfminer.pdfdevice",
    "pdfminer.pdfpage",
    "pdfminer.converter",
    "pdfminer.pdfparser",
    "pdfminer.pdfdocument",
    # Word / DOCX
    "mammoth",
    "lxml",
    "lxml.etree",
    "lxml._elementpath",
    # PowerPoint
    "pptx",
    "pptx.util",
    # Excel
    "openpyxl",
    "xlrd",
    # HTML
    "bs4",
    "markdownify",
    # 圖片
    "PIL",
    "PIL._tkinter_finder",
    "PIL.Image",
    # LLM
    "openai",
    # OCR
    "markitdown_ocr",
    # 其他
    "jinja2",
    "markitdown._base_converter",
]

hiddenimports += extra_hidden

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不需要的重量級依賴
        "pydub",
        "speech_recognition",
        "SpeechRecognition",
        "youtube_transcript_api",
        "azure",
        "azure.ai",
        "azure.identity",
        "azure.core",
        "scipy",
        "matplotlib",
        "notebook",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarkItDownApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不顯示黑色終端機視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MarkItDownApp",
)
