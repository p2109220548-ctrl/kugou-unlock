#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷狗音乐解锁器 —— 图形界面
==========================

面向普通用户的点击式界面：选择文件 → 选择保存位置 → 点击"开始转换"，
全程无需命令行。默认中文界面，可一键切换 English。

直接双击运行（或 `python kugou_unlock_gui.py`）。核心解密逻辑在
kugou_unlock.py 中，本文件只负责界面与交互。

重要 —— 仅限个人使用：只处理你本人拥有合法使用权的本地文件，
解密产物仅限私人播放，请勿二次分发。
"""

# 项目签名（依 LICENSE 条款不得删除或篡改）：
# 开发者 / Author: 鼠鼠shushuu (shushuu) — https://github.com/p2109220548-ctrl
# 仅限个人非商业使用，禁止商用 / Personal non-commercial use only
__author__ = "鼠鼠shushuu (https://github.com/p2109220548-ctrl)"
__license__ = "Personal-NonCommercial-Use-Only (see LICENSE file)"

import ctypes
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import kugou_unlock as core
import kugou_integrity as integrity

# 界面字体：Windows 用微软雅黑，macOS 用苹方（跨平台显示效果一致）
if sys.platform == 'darwin':
    UI_FONT, LOG_FONT = "PingFang SC", "Menlo"
elif os.name == 'nt':
    UI_FONT, LOG_FONT = "Microsoft YaHei UI", "Consolas"
else:
    UI_FONT, LOG_FONT = "Helvetica", "DejaVu Sans Mono"

# ---------------------------------------------------------------------------
# 界面文案（中 / 英）
# ---------------------------------------------------------------------------
I18N = {
    "zh": {
        "app_title": "酷狗音乐解锁器",
        "step1": "① 选择要转换的文件",
        "pick_auto": "自动找到酷狗文件夹",
        "pick_files": "选择文件…",
        "pick_folder": "选择整个文件夹…",
        "picked_files": "已选择 {n} 个加密音频文件",
        "picked_folder": "已选择文件夹：{path}",
        "nothing": "尚未选择文件",
        "step2": "② 选择保存位置",
        "pick_out": "选择输出文件夹…",
        "step3": "③ 选择输出格式",
        "fmt_auto": "保持原始格式（推荐 · 完全无损）",
        "fmt_flac": "FLAC（无损）",
        "fmt_mp3": "MP3（320k，有损）",
        "fmt_wav": "WAV（无损）",
        "fmt_note": "小提示：解密是无损去壳，不会损失音质；转码格式需要电脑装有 FFmpeg。",
        "ffmpeg_missing": "未检测到 FFmpeg，转码格式不可用（“保持原始格式”不受影响）",
        "start": "开始转换",
        "working": "正在转换… {done}/{total}",
        "done_title": "转换完成",
        "done_msg": "转换完成！\n成功 {ok} 个，失败 {fail} 个。\n点击下方「打开输出文件夹」查看歌曲，文件保存在：\n{out}",
        "all_fail_msg": "转换失败：{fail} 个文件未能转换。\n详细信息见下方日志。",
        "open_folder": "打开输出文件夹",
        "auto_found": "已自动找到酷狗文件夹：{path}",
        "auto_not_found": "没自动找到——请手动选择酷狗的下载文件夹（常见如 G:\\KuGou\\KugouMusic）",
        "log_title": "转换日志",
        "key_found": "✓ 已找到酷狗密钥库（可以直接处理 .kgg 文件）",
        "key_missing": "⚠ 未找到酷狗密钥库：处理 .kgg 需要本机装有酷狗客户端",
        "key_manual": "手动指定密钥库…",
        "need_input": "请先选择要转换的文件或文件夹",
        "need_out": "请先选择输出文件夹",
        "err_title": "出错了",
        "legal": "由 鼠鼠shushuu 开发 · 仅限个人使用 · 禁止商用 · 请勿二次分发",
        "file_types": "酷狗加密音频",
        "all_files": "所有文件",
        "log_ok": "✓",
        "log_fail": "✗",
        "log_to": "→",
        "log_start": "开始转换，共 {n} 个文件…",
        "log_finish": "完成：成功 {ok}，失败 {fail}",
        "log_skip": "所选位置没有找到加密音频文件（支持 .kgm/.kgma/.vpr/.kgg）",
        "about": "关于",
        "about_title": "关于 酷狗音乐解锁器",
        "integrity_title": "完整性校验失败",
        "picker_title": "选择要转换的文件",
        "picker_hint": "在所选文件夹里找到 {n} 个加密音频文件，请选中要转换的（可按住 Ctrl / Shift 多选）：",
        "picker_select_all": "全部选择",
        "picker_clear": "清除选择",
        "picker_ok": "确定",
        "picker_cancel": "取消",
        "picker_empty": "这个文件夹里没有找到加密音频文件（支持 .kgm / .kgma / .vpr / .kgg）",
        "picked_from_folder": "已选 {n} / {total} 个文件（来自：{path}）",
    },
    "en": {
        "app_title": "KuGou Unlocker",
        "step1": "① Choose files to convert",
        "pick_auto": "Find my KuGou folder",
        "pick_files": "Choose files…",
        "pick_folder": "Choose a folder…",
        "picked_files": "{n} encrypted audio file(s) selected",
        "picked_folder": "Folder selected: {path}",
        "nothing": "No files selected yet",
        "step2": "② Choose where to save",
        "pick_out": "Choose output folder…",
        "step3": "③ Choose output format",
        "fmt_auto": "Keep original format (recommended · lossless)",
        "fmt_flac": "FLAC (lossless)",
        "fmt_mp3": "MP3 (320k, lossy)",
        "fmt_wav": "WAV (lossless)",
        "fmt_note": "Tip: decryption is a lossless unwrap — quality is never reduced. Transcoding needs FFmpeg installed.",
        "ffmpeg_missing": "FFmpeg not found — transcoding disabled (\"keep original\" still works)",
        "start": "Start conversion",
        "working": "Converting… {done}/{total}",
        "done_title": "Finished",
        "done_msg": "Conversion finished!\n{ok} succeeded, {fail} failed.\nClick \"Open output folder\" below to see your songs.\nFiles saved to:\n{out}",
        "all_fail_msg": "Conversion failed: {fail} file(s) could not be converted.\nSee the log below for details.",
        "open_folder": "Open output folder",
        "auto_found": "KuGou folder found automatically: {path}",
        "auto_not_found": "Not found automatically — please pick the KuGou download folder manually (e.g. C:\\KuGou\\KugouMusic)",
        "log_title": "Log",
        "key_found": "✓ KuGou key database found (.kgg ready to convert)",
        "key_missing": "⚠ KuGou key database not found: converting .kgg needs the KuGou client installed",
        "key_manual": "Locate key database…",
        "need_input": "Please choose files or a folder first",
        "need_out": "Please choose an output folder first",
        "err_title": "Error",
        "ok_title": "Finished",
        "legal": "For files you legally own · Do not redistribute",
        "file_types": "KuGou encrypted audio",
        "all_files": "All files",
        "log_ok": "✓",
        "log_fail": "✗",
        "log_to": "→",
        "log_start": "Starting conversion of {n} file(s)…",
        "log_finish": "Finished: {ok} succeeded, {fail} failed",
        "log_skip": "No encrypted audio files found (.kgm/.kgma/.vpr/.kgg)",
        "about": "About",
        "about_title": "About KuGou Unlocker",
        "integrity_title": "Integrity check failed",
        "picker_title": "Choose files to convert",
        "picker_hint": "Found {n} encrypted audio file(s) in the selected folder. Pick the ones to convert (Ctrl / Shift for multi-select):",
        "picker_select_all": "Select all",
        "picker_clear": "Clear",
        "picker_ok": "OK",
        "picker_cancel": "Cancel",
        "picker_empty": "No encrypted audio files in this folder (.kgm / .kgma / .vpr / .kgg)",
        "picked_from_folder": "{n} / {total} file(s) selected (from: {path})",
    },
}


class App:
    """主窗口：三步向导 + 后台转换线程。"""

    def __init__(self, root):
        self.root = root
        self.lang = "zh"
        self.t = I18N["zh"]
        self.src = None          # 选中的源（文件列表或文件夹路径）
        self.src_kind = None     # 'files' / 'folder'
        self.out_dir = tk.StringVar()
        self.fmt = tk.StringVar(value="auto")
        self.db_override = None  # 手动指定的密钥库路径
        self.has_ffmpeg = True   # 先乐观假设可用，后台检测后修正
        self.key_db = None
        self.events = queue.Queue()
        self.running = False
        self._build()
        self._apply_lang()
        self._check_env_async()

    # ---------------- 界面搭建 ----------------
    def _build(self):
        # 窗口标题常驻署名（依 LICENSE 条款不得移除）
        self.root.title("酷狗音乐解锁器 · 鼠鼠shushuu  |  KuGou Unlocker by shushuu")
        # 窗口尺寸随系统 DPI 缩放自适应（高分屏 125%/150% 缩放下不再偏小）
        try:
            scale = self.root.winfo_fpixels("1i") / 96.0
        except Exception:
            scale = 1.0
        scale = max(1.0, min(scale, 3.0))
        self.root.geometry("%dx%d" % (int(680 * scale), int(700 * scale)))
        self.root.minsize(int(620 * scale), int(620 * scale))

        style = ttk.Style(self.root)
        for theme in (("aqua", "vista", "clam") if sys.platform == "darwin" else ("vista", "clam")):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        # ---- 顶栏：标题 + 语言切换 ----
        top = ttk.Frame(outer)
        top.pack(fill="x")
        self.w_title = ttk.Label(top, text="", font=(UI_FONT, 16, "bold"))
        self.w_title.pack(side="left")
        self.w_lang_label = ttk.Label(top, text="")
        self.w_lang_label.pack(side="right", padx=(0, 4))
        self.w_lang = ttk.Combobox(top, state="readonly", width=10, values=["简体中文", "English"])
        self.w_lang.current(0)
        self.w_lang.pack(side="right")
        self.w_lang.bind("<<ComboboxSelected>>", self._switch_lang)
        self.w_about = ttk.Button(top, command=self._show_about, width=8)
        self.w_about.pack(side="right", padx=(0, 12))

        # ---- 第 1 步：选文件 ----
        box1 = ttk.LabelFrame(outer, padding=10)
        box1.pack(fill="x", pady=(12, 6))
        self.w_step1 = ttk.Label(box1, text="", font=(UI_FONT, 10, "bold"))
        self.w_step1.pack(anchor="w")
        row1 = ttk.Frame(box1)
        row1.pack(fill="x", pady=4)
        self.w_pick_auto = ttk.Button(row1, command=self._pick_auto)
        self.w_pick_auto.pack(side="left", padx=(0, 8))
        self.w_pick_files = ttk.Button(row1, command=self._pick_files)
        self.w_pick_files.pack(side="left", padx=(0, 8))
        self.w_pick_folder = ttk.Button(row1, command=self._pick_folder)
        self.w_pick_folder.pack(side="left")
        self.w_src_info = ttk.Label(box1, text="", foreground="#555555")
        self.w_src_info.pack(anchor="w")

        # ---- 第 2 步：输出位置 ----
        box2 = ttk.LabelFrame(outer, padding=10)
        box2.pack(fill="x", pady=6)
        self.w_step2 = ttk.Label(box2, text="", font=(UI_FONT, 10, "bold"))
        self.w_step2.pack(anchor="w")
        row2 = ttk.Frame(box2)
        row2.pack(fill="x", pady=4)
        self.w_pick_out = ttk.Button(row2, command=self._pick_out)
        self.w_pick_out.pack(side="left", padx=(0, 8))
        self.w_out_info = ttk.Label(row2, text="", foreground="#555555")
        self.w_out_info.pack(side="left", fill="x", expand=True)

        # ---- 第 3 步：输出格式 ----
        box3 = ttk.LabelFrame(outer, padding=10)
        box3.pack(fill="x", pady=6)
        self.w_step3 = ttk.Label(box3, text="", font=(UI_FONT, 10, "bold"))
        self.w_step3.pack(anchor="w")
        self.w_fmt_auto = ttk.Radiobutton(box3, variable=self.fmt, value="auto")
        self.w_fmt_auto.pack(anchor="w", pady=2)
        self.w_fmt_flac = ttk.Radiobutton(box3, variable=self.fmt, value="flac")
        self.w_fmt_flac.pack(anchor="w", pady=2)
        self.w_fmt_mp3 = ttk.Radiobutton(box3, variable=self.fmt, value="mp3")
        self.w_fmt_mp3.pack(anchor="w", pady=2)
        self.w_fmt_wav = ttk.Radiobutton(box3, variable=self.fmt, value="wav")
        self.w_fmt_wav.pack(anchor="w", pady=2)
        self.w_fmt_note = ttk.Label(box3, text="", foreground="#777777", wraplength=int(600 * scale), justify="left")
        self.w_fmt_note.pack(anchor="w", pady=(4, 0))

        # ---- 开始按钮 + 进度 ----
        self.w_start = ttk.Button(outer, command=self._start, style="Accent.TButton")
        self.w_start.pack(fill="x", pady=12, ipady=6)
        self.w_progress = ttk.Progressbar(outer, maximum=100)
        self.w_progress.pack(fill="x")
        self.w_status = ttk.Label(outer, text="")
        self.w_status.pack(anchor="w", pady=(4, 8))

        # ---- 日志 ----
        boxlog = ttk.LabelFrame(outer, padding=8)
        boxlog.pack(fill="both", expand=True)
        self.w_log_title = ttk.Label(boxlog, text="")
        self.w_log_title.pack(anchor="w")
        logwrap = ttk.Frame(boxlog)
        logwrap.pack(fill="both", expand=True)
        self.w_log = tk.Text(logwrap, height=8, state="disabled", wrap="none",
                             font=(LOG_FONT, 9), background="#fafafa")
        scrollbar = ttk.Scrollbar(logwrap, command=self.w_log.yview)
        self.w_log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.w_log.pack(side="left", fill="both", expand=True)

        # ---- 底部：打开输出文件夹 + 密钥库状态 + 法律提示 ----
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        self.w_key_status = ttk.Label(bottom, text="", foreground="#555555")
        self.w_key_status.pack(side="left")
        self.w_key_btn = ttk.Button(bottom, command=self._pick_keydb, width=18)
        self.w_key_btn.pack(side="right")
        self.w_open_out = ttk.Button(bottom, command=self._open_out, width=22, state="disabled")
        self.w_open_out.pack(side="right", padx=(0, 8))
        self.w_legal = ttk.Label(outer, text="", foreground="#999999")
        self.w_legal.pack(anchor="e", pady=(6, 0))

        self.root.after(100, self._poll_events)

    # ---------------- 语言 ----------------
    def _switch_lang(self, _evt=None):
        self.lang = "zh" if self.w_lang.current() == 0 else "en"
        self.t = I18N[self.lang]
        self._apply_lang()

    def _apply_lang(self):
        t = self.t
        self.w_title.config(text=t["app_title"])
        self.w_lang_label.config(text="Language / 语言")
        self.w_about.config(text=t["about"])
        self.w_step1.config(text=t["step1"])
        self.w_pick_auto.config(text=t["pick_auto"])
        self.w_pick_files.config(text=t["pick_files"])
        self.w_pick_folder.config(text=t["pick_folder"])
        self.w_step2.config(text=t["step2"])
        self.w_pick_out.config(text=t["pick_out"])
        self.w_step3.config(text=t["step3"])
        self.w_fmt_auto.config(text=t["fmt_auto"])
        self.w_fmt_flac.config(text=t["fmt_flac"])
        self.w_fmt_mp3.config(text=t["fmt_mp3"])
        self.w_fmt_wav.config(text=t["fmt_wav"])
        self.w_fmt_note.config(text=t["ffmpeg_missing"] if not self.has_ffmpeg else t["fmt_note"])
        self.w_start.config(text=t["start"])
        self.w_log_title.config(text=t["log_title"])
        self.w_key_btn.config(text=t["key_manual"])
        self.w_open_out.config(text=t["open_folder"])
        self.w_legal.config(text=t["legal"])
        self._refresh_src_info()
        self._refresh_out_info()

    # ---------------- 环境检查（后台线程） ----------------
    def _check_env_async(self):
        def work():
            has_ffmpeg = core.check_ffmpeg() is not None
            db = core.discover_kgg_db()
            key_count = 0
            if db:
                try:
                    key_count = len(core.decrypt_kgg_db(db))
                except Exception:
                    db = None
            self.events.put(("env", has_ffmpeg, db, key_count))
        threading.Thread(target=work, daemon=True).start()

    def _apply_env(self, has_ffmpeg, db, key_count):
        self.has_ffmpeg = has_ffmpeg
        self.key_db = db
        t = self.t
        # FFmpeg 不可用时禁用转码选项
        state = "normal" if has_ffmpeg else "disabled"
        for w in (self.w_fmt_flac, self.w_fmt_mp3, self.w_fmt_wav):
            w.config(state=state)
        self.w_fmt_note.config(text=t["ffmpeg_missing"] if not has_ffmpeg else t["fmt_note"])
        # 密钥库状态
        if db:
            self.w_key_status.config(text=t["key_found"] + ("（%d）" % key_count if self.lang == "zh" else " (%d)" % key_count),
                                     foreground="#1a7f37")
        else:
            self.w_key_status.config(text=t["key_missing"], foreground="#b35900")

    # ---------------- 选择交互 ----------------
    def _refresh_src_info(self):
        if self.src is None:
            self.w_src_info.config(text=self.t["nothing"])
        elif self.src_kind == "folder":
            self.w_src_info.config(text=self.t["picked_folder"].format(path=self.src))
        else:
            self.w_src_info.config(text=self.t["picked_files"].format(n=len(self.src)))

    def _refresh_out_info(self):
        self.w_out_info.config(text=self.out_dir.get())

    def _pick_auto(self):
        """一键自动寻找酷狗的下载文件夹（读配置 + 扫描各盘默认位置）。"""
        self.w_src_info.config(text="…")
        self.root.update()
        found = core.discover_kugou_music_dir()
        if found:
            # 找到文件夹后弹出选择窗口：默认全选，用户可挑选部分文件
            self._show_file_picker(found)
        else:
            self.w_src_info.config(text=self.t["auto_not_found"], foreground="#b35900")

    def _open_out(self):
        """打开输出文件夹（转换完成后可用）。"""
        out = self.out_dir.get()
        if out and os.path.isdir(out):
            try:
                if os.name == 'nt':
                    os.startfile(out)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', out])
                else:
                    subprocess.Popen(['xdg-open', out])
            except Exception:
                pass

    def _pick_files(self):
        types = [(self.t["file_types"], "*.kgm *.kgma *.vpr *.kgg"), (self.t["all_files"], "*.*")]
        paths = filedialog.askopenfilenames(filetypes=types)
        if paths:
            self.src = list(paths)
            self.src_kind = "files"
            self._refresh_src_info()

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            # 选完目标文件夹后弹出选择窗口：列出其中的加密文件供勾选（含全部选择）
            self._show_file_picker(os.path.normpath(path))

    def _pick_out(self):
        path = filedialog.askdirectory()
        if path:
            self.out_dir.set(os.path.normpath(path))
            self._refresh_out_info()

    def _pick_keydb(self):
        path = filedialog.askopenfilename(filetypes=[("KGMusicV3.db", "*.db"), ("*", "*.*")])
        if path:
            self.db_override = path
            try:
                n = len(core.decrypt_kgg_db(path))
                self.key_db = path
                self.w_key_status.config(text=self.t["key_found"] + " (%d)" % n, foreground="#1a7f37")
            except Exception as e:
                messagebox.showerror(self.t["err_title"], str(e))

    # ---------------- 文件夹内文件选择窗口 ----------------
    def _show_file_picker(self, folder):
        """选完目标文件夹后弹出：列出其中全部加密音频文件供勾选（默认全选）。

        确定后把选中的文件列表作为转换来源；支持 Ctrl / Shift 多选，
        「全部选择」一键全选。取消则不做任何改动。
        """
        t = self.t
        files = []
        try:
            for name in sorted(os.listdir(folder)):
                if os.path.splitext(name)[1].lower().lstrip('.') in core.AUDIO_EXTS:
                    full = os.path.join(folder, name)
                    if os.path.isfile(full):
                        try:
                            size_mb = os.path.getsize(full) / 1048576.0
                            label = "%s   (%.1f MB)" % (name, size_mb)
                        except OSError:
                            label = name
                        files.append((full, label))
        except OSError:
            pass
        if not files:
            messagebox.showinfo(t["app_title"], t["picker_empty"])
            return

        try:
            scale = self.root.winfo_fpixels("1i") / 96.0
        except Exception:
            scale = 1.0
        scale = max(1.0, min(scale, 3.0))

        dlg = tk.Toplevel(self.root)
        dlg.title(t["picker_title"])
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(True, True)
        dlg.geometry("%dx%d+%d+%d" % (
            int(620 * scale), int(460 * scale),
            self.root.winfo_x() + 30, self.root.winfo_y() + 40))

        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=t["picker_hint"].format(n=len(files)),
                  wraplength=int(580 * scale), justify="left").pack(anchor="w", pady=(0, 6))

        listwrap = ttk.Frame(frame)
        listwrap.pack(fill="both", expand=True)
        lb = tk.Listbox(listwrap, selectmode="extended", font=(UI_FONT, 10),
                        activestyle="dotnone", exportselection=False)
        sb = ttk.Scrollbar(listwrap, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        for _full, label in files:
            lb.insert("end", label)
        lb.selection_set(0, "end")  # 默认全部选中

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))

        def select_all(_evt=None):
            lb.selection_set(0, "end")
            lb.see(0)

        def clear_sel():
            lb.selection_clear(0, "end")

        def confirm(_evt=None):
            sel = lb.curselection()
            if not sel:
                return
            self.src = [files[i][0] for i in sel]
            self.src_kind = "files"
            self.w_src_info.config(
                text=t["picked_from_folder"].format(n=len(sel), total=len(files), path=folder),
                foreground="#1a7f37")
            dlg.destroy()

        b_all = ttk.Button(btns, command=select_all)
        b_all.pack(side="left", padx=(0, 6))
        b_clear = ttk.Button(btns, command=clear_sel)
        b_clear.pack(side="left")
        b_ok = ttk.Button(btns, command=confirm, style="Accent.TButton")
        b_ok.pack(side="right")
        b_cancel = ttk.Button(btns, command=dlg.destroy)
        b_cancel.pack(side="right", padx=(0, 8))

        lb.bind("<Double-Button-1>", confirm)
        dlg.bind("<Return>", confirm)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        b_all.focus_set()

    # ---------------- 关于 ----------------
    def _show_about(self):
        """关于弹窗：官方 logo、版本、署名、许可与免责声明。"""
        top = tk.Toplevel(self.root)
        top.title(self.t["about_title"])
        top.transient(self.root)
        top.resizable(False, False)
        top.grab_set()
        pad = ttk.Frame(top, padding=16)
        pad.pack(fill="both", expand=True)
        # 官方 logo 照片（docs/logo.png，受完整性保护，缺失时软件已拒绝启动）
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(core.__file__)),
                                     "docs", "logo.png")
            photo = tk.PhotoImage(file=logo_path)
            # 按 96 缩放显示（subsample 只支持整数倍缩小）
            factor = max(1, photo.width() // 150)
            photo = photo.subsample(factor, factor)
            tk.Label(pad, image=photo, background="#ffffff").pack()
            top._logo_ref = photo  # 防 GC
        except Exception:
            pass
        ttk.Label(pad, text=integrity.banner(core.__version__),
                  justify="center", font=(UI_FONT, 9)).pack(pady=(8, 4))
        b = ttk.Button(pad, text=self.t["picker_ok"], command=top.destroy)
        b.pack(pady=(4, 0))
        top.update_idletasks()
        top.geometry("+%d+%d" % (self.root.winfo_x() + 60, self.root.winfo_y() + 60))

    # ---------------- 转换 ----------------
    def _log(self, line):
        self.w_log.config(state="normal")
        self.w_log.insert("end", line + "\n")
        self.w_log.see("end")
        self.w_log.config(state="disabled")

    def _start(self):
        if self.running:
            return
        t = self.t
        if not self.src:
            messagebox.showwarning(t["app_title"], t["need_input"])
            return
        if not self.out_dir.get():
            messagebox.showwarning(t["app_title"], t["need_out"])
            return
        self.running = True
        self.w_start.config(state="disabled")
        self.w_progress.config(value=0)
        src, out, fmt = self.src, self.out_dir.get(), self.fmt.get()
        db = self.db_override or self.key_db
        self._log("— " + t["log_start"].format(n="…"))

        def work():
            try:
                def progress(done, total, path, status, info):
                    self.events.put(("progress", done, total, path, status, info))
                ok, fail = core.batch_convert(src, out, target_fmt=fmt, db_path=db,
                                              progress_cb=progress)
                self.events.put(("done", ok, fail, out))
            except Exception as e:
                self.events.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    # ---------------- 事件轮询（UI 线程） ----------------
    def _poll_events(self):
        try:
            while True:
                evt = self.events.get_nowait()
                kind = evt[0]
                t = self.t
                if kind == "env":
                    self._apply_env(evt[1], evt[2], evt[3])
                elif kind == "progress":
                    _, done, total, path, status, info = evt
                    if total:
                        self.w_progress.config(value=100.0 * done / total)
                        self.w_status.config(text=t["working"].format(done=done, total=total))
                    name = os.path.basename(path)
                    mark = t["log_ok"] if status == "ok" else t["log_fail"]
                    self._log("%s %s %s %s" % (mark, name, t["log_to"], info))
                elif kind == "done":
                    _, ok, fail, out = evt
                    if fail == 0:
                        self.w_progress.config(value=100)
                    self.w_status.config(text=t["log_finish"].format(ok=ok, fail=fail))
                    self._log("— " + t["log_finish"].format(ok=ok, fail=fail))
                    self.running = False
                    self.w_start.config(state="normal")
                    # 转换完成后启用"打开输出文件夹"按钮（不再用是/否弹窗，避免点错）
                    self.w_open_out.config(state="normal")
                    if fail == 0:
                        messagebox.showinfo(t["done_title"],
                                            t["done_msg"].format(ok=ok, fail=fail, out=out))
                    else:
                        messagebox.showwarning(t["done_title"], t["all_fail_msg"].format(fail=fail))
                elif kind == "error":
                    self.running = False
                    self.w_start.config(state="normal")
                    messagebox.showerror(t["err_title"], evt[1])
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)


def _enable_windows_high_dpi():
    """声明 DPI 感知（Windows）：高分屏缩放下界面清晰不发糊、控件不错位。

    必须在创建 tk.Tk() 之前调用。此前进程未声明 DPI 感知时，Windows 会对
    整个窗口做位图拉伸，界面模糊且布局偏移。
    """
    if os.name != "nt":
        return
    try:  # Win10 1703+：Per-Monitor V2，多屏不同缩放率也正确
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:  # Win 8.1+ 兜底
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:  # 更旧的系统兜底
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _show_integrity_error(problems):
    """完整性校验失败：弹窗展示原因与署名后退出，不进入主界面。"""
    text = integrity.fail_text(problems)
    try:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("酷狗音乐解锁器 · 完整性校验失败", text)
        r.destroy()
    except Exception:
        pass
    sys.exit(2)


def main():
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    # 防篡改保护：程序/文档/许可被修改或缺失时拒绝启动（详见 kugou_integrity.py）
    ok, problems = integrity.verify()
    if not ok:
        _show_integrity_error(problems)
        return
    _enable_windows_high_dpi()
    root = tk.Tk()
    app = App(root)
    app._log("— " + integrity.AUTHOR_LINE)
    app._log("— " + integrity.DISCLAIMER)
    root.mainloop()


if __name__ == "__main__":
    main()
