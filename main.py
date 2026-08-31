# -*- coding: utf-8 -*-
"""
🎬 TSub (Subtitle Translation Studio) - Standalone Edition
Unified Subtitle Localization Suite featuring Studio Mode & High-Speed Batch Pipeline (TRun Engine).
"""

import os
import sys
import re
import json
from typing import List, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QTextEdit, QLabel, QPushButton, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QSplitter, QHeaderView, QAbstractItemView,
    QProgressBar, QMenu, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QThreadPool, QModelIndex
from PyQt6.QtGui import QAction, QKeySequence, QIcon

from srt_engine import SrtEngine, SrtEntry, calculate_cps, strip_tags
from tsub_table_model import SubtitleTableModel, SubtitleFilterProxyModel
from config_manager import ConfigManager
from core_ai import CoreAI, ApiWorker, ThreadSafeWorkerSignalsForwarder
from tsub_dialogs import SettingsDialog, PromptSettingsDialog, GlossaryDock, TranslationOptionsDialog
from tsub_batch_view import BatchTranslationView

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', 'Tahoma', sans-serif;
    font-size: 13px;
}
QTableView {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    gridline-color: #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #11111b;
    color: #bac2de;
    padding: 6px;
    border: 1px solid #313244;
    font-weight: bold;
}
QTextEdit, QLineEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #585b70;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border-color: #313244;
}
QComboBox {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
}
QComboBox::drop-down {
    border: none;
}
QProgressBar {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}
QDockWidget {
    color: #cdd6f4;
    font-weight: bold;
}
QDockWidget::title {
    background: #11111b;
    padding: 6px;
    border: 1px solid #313244;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #11111b;
    color: #bac2de;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
    border-bottom: 2px solid #89b4fa;
}
"""
class TSubApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 TSub - Subtitle Translation Studio (Standalone Edition)")
        self.resize(1240, 840)
        self.setStyleSheet(DARK_STYLE)

        self.threadpool = QThreadPool()
        self._workers = {}
        self._batch_total = 0
        self._batch_completed = 0
        self._batch_errors = []
        self._is_closing = False
        
        self.current_filepath: Optional[str] = None
        self.current_encoding: str = "utf-8-sig"
        self.current_source_row: int = -1

        self.model = SubtitleTableModel([], self)
        self.proxy = SubtitleFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)

        self.init_ui()
        self.init_shortcuts()

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Header Toolbar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.btn_open = QPushButton("📂 Open .SRT")
        self.btn_open.clicked.connect(self.open_srt_dialog)
        header_layout.addWidget(self.btn_open)

        self.btn_save = QPushButton("💾 Save .SRT")
        self.btn_save.clicked.connect(self.save_srt)
        header_layout.addWidget(self.btn_save)

        self.btn_export_menu = QPushButton("📤 Export As... ▾")
        self.export_menu = QMenu(self)
        self.export_menu.addAction("Export Translation Only (.srt)", lambda: self.export_srt_as("trans_only"))
        self.export_menu.addAction("Export Dual Subtitle (Thai Top / Eng Bottom)", lambda: self.export_srt_as("dual_thai_top"))
        self.export_menu.addAction("Export Dual Subtitle (Eng Top / Thai Bottom)", lambda: self.export_srt_as("dual_eng_top"))
        self.export_menu.addAction("Export Original Source Only (.srt)", lambda: self.export_srt_as("source_only"))
        self.btn_export_menu.setMenu(self.export_menu)
        header_layout.addWidget(self.btn_export_menu)

        header_layout.addSpacing(10)

        # Profile Quick Selector
        header_layout.addWidget(QLabel("📁 Profile:"))
        self.cbo_main_profile = QComboBox()
        self.cbo_main_profile.setMinimumWidth(130)
        self.refresh_main_profile_list()
        self.cbo_main_profile.currentTextChanged.connect(self.on_main_profile_changed)
        header_layout.addWidget(self.cbo_main_profile)

        header_layout.addSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 ค้นหาคำศัพท์ / ซับไตเติ้ล...")
        self.txt_search.textChanged.connect(self.proxy.set_search_keyword)
        header_layout.addWidget(self.txt_search, stretch=1)

        self.cbo_filter = QComboBox()
        self.cbo_filter.addItems(["ทั้งหมด (All)", "ยังไม่แปล (Untranslated)", "แปลแล้ว (Translated)", "⚠️ ความเร็วเกินเกณฑ์ (High CPS)"])
        self.cbo_filter.currentIndexChanged.connect(self.on_filter_changed)
        header_layout.addWidget(self.cbo_filter)

        self.chk_guide_mode = QCheckBox("โหมดไกด์ (AI Ref Only)")
        self.chk_guide_mode.setToolTip("เมื่อเปิดใช้งาน คำแปลจะลงที่ช่อง AI Reference โดยไม่ทับช่องคำแปลจริง")
        header_layout.addWidget(self.chk_guide_mode)

        header_layout.addSpacing(10)

        self.btn_prompts = QPushButton("🤖 Prompts & Lore")
        self.btn_prompts.setToolTip("ตั้งค่า System Prompt, Cinematic Tones, และบริบทเนื้อเรื่อง (Lore Context) (Ctrl+P)")
        self.btn_prompts.clicked.connect(self.open_prompts_dialog)
        header_layout.addWidget(self.btn_prompts)

        self.btn_glossary = QPushButton("📚 Glossary")
        self.btn_glossary.clicked.connect(self.toggle_glossary_dock)
        header_layout.addWidget(self.btn_glossary)

        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.btn_settings)

        main_layout.addLayout(header_layout)

        # ── Main Two-Page Tabs (Studio View vs Batch Pipeline) ───────────────
        self.main_tabs = QTabWidget()

        # ── Page 1: Subtitle Studio (Line-by-Line & Grid) ─────────────────────
        p1_widget = QWidget()
        p1_layout = QVBoxLayout(p1_widget)
        p1_layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table View
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 300)
        self.table.setColumnWidth(5, 300)
        self.table.selectionModel().currentChanged.connect(self.on_table_row_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_table_context_menu)
        splitter.addWidget(self.table)

        # Bottom Editors
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(6)

        editor_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Source Editor
        p_src = QWidget()
        l_src = QVBoxLayout(p_src)
        l_src.setContentsMargins(0, 0, 0, 0)
        self.lbl_src_info = QLabel("📝 Original Subtitle (Source):")
        self.lbl_src_info.setStyleSheet("font-weight: bold; color: #89b4fa;")
        l_src.addWidget(self.lbl_src_info)
        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setStyleSheet("background-color: #181825; color: #a6adc8; font-size: 14px;")
        l_src.addWidget(self.txt_source)
        editor_splitter.addWidget(p_src)

        # Translation Editor
        p_trans = QWidget()
        l_trans = QVBoxLayout(p_trans)
        l_trans.setContentsMargins(0, 0, 0, 0)
        t_header = QHBoxLayout()
        self.lbl_trans_info = QLabel("🇹🇭 Thai Translation:")
        self.lbl_trans_info.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        t_header.addWidget(self.lbl_trans_info)
        t_header.addStretch()
        self.lbl_cps_meter = QLabel("CPS: 0.0 | Chars: 0 | Lines: 0")
        self.lbl_cps_meter.setStyleSheet("font-weight: bold; color: #fab387;")
        t_header.addWidget(self.lbl_cps_meter)
        l_trans.addLayout(t_header)

        self.txt_trans = QTextEdit()
        self.txt_trans.setStyleSheet("font-size: 14px;")
        self.txt_trans.textChanged.connect(self.on_trans_editor_changed)
        l_trans.addWidget(self.txt_trans)
        editor_splitter.addWidget(p_trans)

        # AI Reference Box
        p_ai = QWidget()
        l_ai = QVBoxLayout(p_ai)
        l_ai.setContentsMargins(0, 0, 0, 0)
        self.lbl_ai_info = QLabel("🤖 AI Reference:")
        self.lbl_ai_info.setStyleSheet("font-weight: bold; color: #cba6f7;")
        l_ai.addWidget(self.lbl_ai_info)
        self.txt_ai = QTextEdit()
        self.txt_ai.setStyleSheet("background-color: #181825; color: #cdd6f4; font-size: 14px;")
        self.txt_ai.textChanged.connect(self.on_ai_editor_changed)
        l_ai.addWidget(self.txt_ai)
        editor_splitter.addWidget(p_ai)

        bottom_layout.addWidget(editor_splitter)

        # Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.btn_smart_trans = QPushButton("⚡ แปลอัจฉริยะ (Smart Translate)")
        self.btn_smart_trans.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 8px 16px;")
        self.btn_smart_trans.clicked.connect(self.translate_smart)
        actions_layout.addWidget(self.btn_smart_trans)

        self.btn_opt_trans = QPushButton("🎭 แปล 3 สไตล์ (Options)")
        self.btn_opt_trans.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 8px 14px;")
        self.btn_opt_trans.clicked.connect(self.translate_options)
        actions_layout.addWidget(self.btn_opt_trans)

        self.btn_cinematic_menu = QPushButton("🎬 โทนภาพยนตร์ ▾")
        self.btn_cinematic_menu.setStyleSheet("background-color: #fab387; color: #11111b; font-weight: bold; padding: 8px 14px;")
        self.cinematic_menu = QMenu(self)
        self.cinematic_menu.addAction("บทพูดธรรมชาติ (Natural Dialogue)", lambda: self.translate_cinematic("natural"))
        self.cinematic_menu.addAction("ดิบเถื่อน / แอ็กชัน (Gritty / Action)", lambda: self.translate_cinematic("gritty"))
        self.cinematic_menu.addAction("ย้อนยุค / แฟนตาซี (Fantasy / Archaic)", lambda: self.translate_cinematic("fantasy"))
        self.cinematic_menu.addAction("สแลง / วัยรุ่น (Casual / Slang)", lambda: self.translate_cinematic("casual_slang"))
        self.cinematic_menu.addAction("สุภาพ / ทางการ (Formal)", lambda: self.translate_cinematic("formal"))
        self.cinematic_menu.addAction("กลอน / บทกวี (Poetic Verse)", lambda: self.translate_cinematic("poem"))
        self.cinematic_menu.addAction("ประกาศระบบ / หุ่นยนต์ (Robotic AI)", lambda: self.translate_cinematic("robotic"))
        self.btn_cinematic_menu.setMenu(self.cinematic_menu)
        actions_layout.addWidget(self.btn_cinematic_menu)

        self.btn_autowrap = QPushButton("⏱️ ตัดคำ 2 บรรทัด (Wrap)")
        self.btn_autowrap.setToolTip("ตัดคำบรรยายภาษาไทยให้อยู่ในกรอบ 2 บรรทัดอย่างสวยงาม")
        self.btn_autowrap.clicked.connect(self.autowrap_current_or_selection)
        actions_layout.addWidget(self.btn_autowrap)

        actions_layout.addStretch()

        self.btn_prev = QPushButton("◀ ก่อนหน้า (Alt+Up)")
        self.btn_prev.clicked.connect(self.goto_prev_row)
        actions_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("ถัดไป (Alt+Down) ▶")
        self.btn_next.clicked.connect(self.goto_next_row)
        actions_layout.addWidget(self.btn_next)

        bottom_layout.addLayout(actions_layout)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        p1_layout.addWidget(splitter)
        self.main_tabs.addTab(p1_widget, "🎬 Subtitle Studio (ตรวจสอบ & แปลรายบรรทัด)")

        # ── Page 2: Batch Pipeline (TRun Style) ───────────────────────────────
        self.batch_view = BatchTranslationView(self)
        self.batch_view.subtitles_updated.connect(self.on_batch_subtitles_updated)
        self.main_tabs.addTab(self.batch_view, "⚡ Batch Pipeline (แปลไฟล์ข้อความเยอะแบบ TRun)")

        main_layout.addWidget(self.main_tabs)

        # Progress Bar & Dock
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(16)
        main_layout.addWidget(self.progress_bar)

        self.statusBar().showMessage("🎬 พร้อมใช้งาน — กรุณาเปิดไฟล์ .srt")

        self.dock_glossary = GlossaryDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_glossary)
        self.dock_glossary.hide()
    def on_batch_subtitles_updated(self, updated_entries: list):
        self.model.set_entries(updated_entries)
        self.statusBar().showMessage(f"อัปเดตข้อมูลจาก Batch Pipeline เข้าสู่ Studio เรียบร้อย ({len(updated_entries)} ซับไตเติ้ล)", 4000)

    def refresh_main_profile_list(self):
        profiles = ConfigManager.get_profile_list()
        active = ConfigManager.get_active_profile_name()
        self.cbo_main_profile.blockSignals(True)
        self.cbo_main_profile.clear()
        self.cbo_main_profile.addItems(profiles)
        if active in profiles:
            self.cbo_main_profile.setCurrentText(active)
        self.cbo_main_profile.blockSignals(False)

    def on_main_profile_changed(self, prof_name: str):
        if not prof_name: return
        ConfigManager.set_active_profile_name(prof_name)
        if hasattr(self, 'dock_glossary'):
            self.dock_glossary.load_glossary()
        prof = ConfigManager.get_active_profile_data()
        src = prof.get("source_language", "English")
        tgt = prof.get("target_language", "Thai")
        self.statusBar().showMessage(f"สลับไปใช้โปรไฟล์: '{prof_name}' ({src} -> {tgt})", 3000)

    def init_shortcuts(self):
        act_open = QAction(self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.open_srt_dialog)
        self.addAction(act_open)

        act_save = QAction(self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.save_srt)
        self.addAction(act_save)

        act_prompts = QAction(self)
        act_prompts.setShortcut(QKeySequence("Ctrl+P"))
        act_prompts.triggered.connect(self.open_prompts_dialog)
        self.addAction(act_prompts)

        act_trans = QAction(self)
        act_trans.setShortcut(QKeySequence("Ctrl+Return"))
        act_trans.triggered.connect(self.translate_smart)
        self.addAction(act_trans)

        act_opt = QAction(self)
        act_opt.setShortcut(QKeySequence("F3"))
        act_opt.triggered.connect(self.translate_options)
        self.addAction(act_opt)

        act_prev = QAction(self)
        act_prev.setShortcut(QKeySequence("Alt+Up"))
        act_prev.triggered.connect(self.goto_prev_row)
        self.addAction(act_prev)

        act_next = QAction(self)
        act_next.setShortcut(QKeySequence("Alt+Down"))
        act_next.triggered.connect(self.goto_next_row)
        self.addAction(act_next)

    def open_srt_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Subtitle File", "", "SubRip Subtitle (*.srt);;All Files (*.*)"
        )
        if filepath:
            self.load_srt_file(filepath)

    def load_srt_file(self, filepath: str):
        try:
            entries, enc = SrtEngine.load_srt(filepath)
            self.current_filepath = filepath
            self.current_encoding = enc
            self.model.set_entries(entries)
            self.setWindowTitle(f"🎬 TSub - [{os.path.basename(filepath)}] ({len(entries)} Subtitles) - Standalone Edition")
            self.statusBar().showMessage(f"โหลดไฟล์สำเร็จ: {len(entries)} รายการ (Encoding: {enc})", 4000)
            
            # Sync into Batch View
            self.batch_view.set_active_file(filepath, entries)

            if entries:
                first_idx = self.proxy.index(0, 0)
                self.table.setCurrentIndex(first_idx)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading SRT", f"ไม่สามารถเปิดไฟล์ .srt ได้:\n{e}")

    def save_srt(self):
        if not self.current_filepath:
            self.export_srt_as("trans_fallback_source")
            return

        try:
            SrtEngine.save_srt(
                self.current_filepath, self.model.entries,
                mode="trans_fallback_source", encoding=self.current_encoding
            )
            self.model.is_dirty = False
            self.statusBar().showMessage(f"บันทึกไฟล์สำเร็จ: {self.current_filepath}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"ไม่สามารถบันทึกไฟล์ได้:\n{e}")

    def export_srt_as(self, mode: str):
        if not self.model.entries:
            QMessageBox.warning(self, "No Data", "ไม่มีข้อมูลซับไตเติ้ลให้ส่งออก")
            return

        default_name = "subtitle_translated.srt"
        if self.current_filepath:
            base, _ = os.path.splitext(self.current_filepath)
            if mode == "dual_thai_top":
                default_name = f"{base}_dual_th.srt"
            elif mode == "dual_eng_top":
                default_name = f"{base}_dual_en.srt"
            elif mode == "trans_only":
                default_name = f"{base}_th.srt"
            else:
                default_name = f"{base}_export.srt"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Subtitle As", default_name, "SubRip Subtitle (*.srt);;All Files (*.*)"
        )
        if filepath:
            try:
                SrtEngine.save_srt(filepath, self.model.entries, mode=mode, encoding="utf-8-sig")
                self.statusBar().showMessage(f"ส่งออกไฟล์สำเร็จ: {filepath}", 4000)
                QMessageBox.information(self, "Export Successful", f"ส่งออกไฟล์เรียบร้อยแล้ว:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"เกิดข้อผิดพลาดในการส่งออก:\n{e}")

    def on_table_row_changed(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return
        source_row = self.proxy.mapToSource(current).row()
        if 0 <= source_row < len(self.model.entries):
            self.current_source_row = source_row
            entry = self.model.entries[source_row]

            self.lbl_src_info.setText(f"📝 Original Subtitle (#{entry.idx} | {entry.timecode_range} | {entry.duration_sec:.1f}s):")
            
            self.txt_source.blockSignals(True)
            self.txt_source.setPlainText(entry.source)
            self.txt_source.blockSignals(False)

            self.txt_trans.blockSignals(True)
            self.txt_trans.setPlainText(entry.trans)
            self.txt_trans.blockSignals(False)

            self.txt_ai.blockSignals(True)
            self.txt_ai.setPlainText(entry.ai_ref)
            self.txt_ai.blockSignals(False)

            self.update_cps_meter(entry.trans, entry.duration_sec)

    def on_trans_editor_changed(self):
        if self.current_source_row < 0 or self.current_source_row >= len(self.model.entries):
            return
        new_text = self.txt_trans.toPlainText()
        self.model.update_trans(self.current_source_row, new_text)
        entry = self.model.entries[self.current_source_row]
        self.update_cps_meter(new_text, entry.duration_sec)

    def on_ai_editor_changed(self):
        if self.current_source_row < 0 or self.current_source_row >= len(self.model.entries):
            return
        new_text = self.txt_ai.toPlainText()
        self.model.update_ai_ref(self.current_source_row, new_text)

    def update_cps_meter(self, text: str, duration_sec: float):
        clean = strip_tags(text)
        cps = calculate_cps(text, duration_sec)
        chars = len(clean)
        lines = len(text.strip().split('\n')) if text.strip() else 0

        color = "#a6e3a1"
        if cps > 25.0:
            color = "#f38ba8"
        elif cps > 20.0:
            color = "#fab387"

        self.lbl_cps_meter.setStyleSheet(f"font-weight: bold; color: {color};")
        self.lbl_cps_meter.setText(f"CPS: {cps:.1f} | Chars: {chars} | Lines: {lines}")

    def on_filter_changed(self, idx: int):
        modes = ["all", "untranslated", "translated", "high_cps"]
        if 0 <= idx < len(modes):
            self.proxy.set_filter_mode(modes[idx])

    def goto_prev_row(self):
        cur = self.table.currentIndex()
        if cur.isValid() and cur.row() > 0:
            new_idx = self.proxy.index(cur.row() - 1, cur.column())
            self.table.setCurrentIndex(new_idx)

    def goto_next_row(self):
        cur = self.table.currentIndex()
        if cur.isValid() and cur.row() < self.proxy.rowCount() - 1:
            new_idx = self.proxy.index(cur.row() + 1, cur.column())
            self.table.setCurrentIndex(new_idx)

    def open_table_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("⚡ แปลแถวที่เลือก (Smart Translate Selected)", self.translate_smart)
        menu.addAction("🎭 แปล 3 สไตล์ (Options)", self.translate_options)
        
        cin_menu = menu.addMenu("🎬 แปลโทนภาพยนตร์ (Cinematic Tones)")
        cin_menu.addAction("บทพูดธรรมชาติ (Natural)", lambda: self.translate_cinematic("natural"))
        cin_menu.addAction("ดิบเถื่อน / แอ็กชัน (Gritty)", lambda: self.translate_cinematic("gritty"))
        cin_menu.addAction("ย้อนยุค / แฟนตาซี (Fantasy)", lambda: self.translate_cinematic("fantasy"))
        cin_menu.addAction("สแลง / วัยรุ่น (Casual Slang)", lambda: self.translate_cinematic("casual_slang"))
        cin_menu.addAction("สุภาพ / ทางการ (Formal)", lambda: self.translate_cinematic("formal"))
        cin_menu.addAction("กลอน / บทกวี (Poetic)", lambda: self.translate_cinematic("poem"))

        menu.addSeparator()
        menu.addAction("⏱️ ตัดคำบรรยาย 2 บรรทัด (Auto Line-Break)", self.autowrap_current_or_selection)
        menu.addAction("🧹 ล้างคำแปลแถวที่เลือก (Clear Translation)", self.clear_selected_translations)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def clear_selected_translations(self):
        selected_indexes = self.table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        for idx in selected_indexes:
            s_row = self.proxy.mapToSource(idx).row()
            self.model.update_trans(s_row, "")
        if self.current_source_row >= 0:
            self.txt_trans.setPlainText("")
        self.statusBar().showMessage(f"ล้างคำแปล {len(selected_indexes)} รายการเรียบร้อย", 3000)
    def _get_dynamic_glossary(self, text: str) -> str:
        glossary = ConfigManager.load_glossary()
        if not glossary:
            return ""
        
        matches = []
        for eng, th in glossary.items():
            if re.search(r'\b' + re.escape(eng) + r'\b', text, re.IGNORECASE):
                matches.append(f"- {eng} -> {th}")

        if matches:
            return "GLOSSARY (You MUST use these exact translations for the terms):\n" + "\n".join(matches)
        return ""

    def _build_prompt(self, entry: SrtEntry, prompt_type: str = "main", mode_key: str = "natural") -> str:
        prof = ConfigManager.get_active_profile_data()
        lore = prof.get("project_lore", "").strip()
        lore_section = f"\n[STORY & WORLD LORE CONTEXT]\n{lore}\n" if lore else ""
        src_lang = prof.get("source_language", "English")
        tgt_lang = prof.get("target_language", "Thai")

        if prompt_type == "options":
            tpl = prof.get("options_prompt", "")
        elif prompt_type == "cinematic":
            modes = prof.get("cinematic_modes", {})
            tone_desc = modes.get(mode_key, f"Translate into natural, conversational {tgt_lang} dialogue.")
            tpl = f"""You are a Master-Level Subtitle Specialist translating from {src_lang} into {tgt_lang}.
Tone Directive: {tone_desc}
Context ID: '{{id}}'. Duration: {{duration}}s.

CRITICAL SUBTITLE RULES:
1. Length: Keep the translation concise (max 2 lines) so it matches the {{duration}}s screen time.
2. Tags: Preserve all HTML tags (<i>, <b>, <font>) exactly as given.
3. Return ONLY the final {tgt_lang} subtitle text. No markdown, no explanations, no quotes.

{{lore}}[GLOSSARY TO USE]

Original Subtitle ({src_lang}):
{{source_text}}"""
        else:
            tpl = prof.get("main_prompt", "")

        # Replacements
        prompt = tpl.replace('{id}', f"sub_{entry.idx}").replace('{duration}', f"{entry.duration_sec:.1f}").replace('{source_text}', entry.source)
        prompt = prompt.replace('{lore}', lore_section)
        
        dyn_glos = self._get_dynamic_glossary(entry.source)
        if "[GLOSSARY TO USE]" in prompt:
            prompt = prompt.replace('[GLOSSARY TO USE]', dyn_glos if dyn_glos else '')
        elif dyn_glos:
            prompt = f"{dyn_glos}\n\n{prompt}"

        return prompt

    def translate_smart(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            if self.current_source_row >= 0:
                self.translate_single_row(self.current_source_row)
            return

        rows = sorted(list(set(self.proxy.mapToSource(idx).row() for idx in selected)))
        if len(rows) == 1:
            self.translate_single_row(rows[0])
        else:
            self.translate_batch_rows(rows)

    def translate_single_row(self, row: int):
        if not (0 <= row < len(self.model.entries)):
            return
        entry = self.model.entries[row]
        if not entry.source.strip():
            return

        cfg = ConfigManager.load_config()
        self.btn_smart_trans.setEnabled(False)
        self.statusBar().showMessage(f"กำลังแปลซับไตเติ้ล #{entry.idx}...")

        prompt = self._build_prompt(entry, "main")

        is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")
        worker = ApiWorker(CoreAI.generate_content, cfg, prompt, is_local=is_local)
        
        forwarder = ThreadSafeWorkerSignalsForwarder(
            on_success=lambda reply, r=row: self._on_single_success(reply, r),
            on_error=lambda err: self._on_single_error(err),
            parent=self
        )
        worker.signals.finished.connect(forwarder.handle_finished)
        worker.signals.error.connect(forwarder.handle_error)
        wid = id(worker)
        worker.signals.finished.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        worker.signals.error.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        self._workers[wid] = worker
        self.threadpool.start(worker)

    def _on_single_success(self, reply: str, row: int):
        self.btn_smart_trans.setEnabled(True)
        translated = re.sub(r'^"|"$', '', reply.strip())
        
        glossary = ConfigManager.load_glossary()
        for eng, th in glossary.items():
            if th:
                translated = re.sub(re.escape(eng), th, translated, flags=re.IGNORECASE)

        if self.chk_guide_mode.isChecked():
            self.model.update_ai_ref(row, translated)
            if row == self.current_source_row:
                self.txt_ai.setPlainText(translated)
        else:
            self.model.update_trans(row, translated)
            if row == self.current_source_row:
                self.txt_trans.setPlainText(translated)

        self.statusBar().showMessage(f"แปลซับไตเติ้ล #{self.model.entries[row].idx} สำเร็จ!", 3000)

    def _on_single_error(self, err: str):
        self.btn_smart_trans.setEnabled(True)
        QMessageBox.warning(self, "Translation Error", f"เกิดข้อผิดพลาดในการแปล:\n{err}")

    def translate_batch_rows(self, rows: List[int]):
        valid_rows = [r for r in rows if self.model.entries[r].source.strip()]
        if not valid_rows:
            return

        if len(valid_rows) > 5:
            reply = QMessageBox.question(
                self, "Confirm Batch Translation",
                f"ต้องการแปลซับไตเติ้ล {len(valid_rows)} รายการที่เลือกพร้อมกันหรือไม่?\n(หรือสามารถสลับไปที่แท็บ '⚡ Batch Pipeline' เพื่อความเร็วสูง)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        cfg = ConfigManager.load_config()
        self._batch_total = len(valid_rows)
        self._batch_completed = 0
        self._batch_errors = []

        self.btn_smart_trans.setEnabled(False)
        self.btn_opt_trans.setEnabled(False)
        self.btn_cinematic_menu.setEnabled(False)
        self.progress_bar.setMaximum(self._batch_total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")

        for row in valid_rows:
            entry = self.model.entries[row]
            prompt = self._build_prompt(entry, "main")

            worker = ApiWorker(CoreAI.generate_content, cfg, prompt, is_local=is_local)
            forwarder = ThreadSafeWorkerSignalsForwarder(
                on_success=lambda reply, r=row: self._on_batch_row_success(reply, r),
                on_error=lambda err, r=row: self._on_batch_row_error(err, r),
                parent=self
            )
            worker.signals.finished.connect(forwarder.handle_finished)
            worker.signals.error.connect(forwarder.handle_error)
            wid = id(worker)
            worker.signals.finished.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
            worker.signals.error.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
            self._workers[wid] = worker
            self.threadpool.start(worker)

    def _on_batch_row_success(self, reply: str, row: int):
        if self._is_closing: return
        translated = re.sub(r'^"|"$', '', reply.strip())
        
        glossary = ConfigManager.load_glossary()
        for eng, th in glossary.items():
            if th:
                translated = re.sub(re.escape(eng), th, translated, flags=re.IGNORECASE)

        if self.chk_guide_mode.isChecked():
            self.model.update_ai_ref(row, translated)
            if row == self.current_source_row:
                self.txt_ai.setPlainText(translated)
        else:
            self.model.update_trans(row, translated)
            if row == self.current_source_row:
                self.txt_trans.setPlainText(translated)

        self._batch_completed += 1
        self._update_batch_progress()

    def _on_batch_row_error(self, err: str, row: int):
        if self._is_closing: return
        self._batch_errors.append((row, str(err)))
        self._batch_completed += 1
        self._update_batch_progress()

    def _update_batch_progress(self):
        self.progress_bar.setValue(self._batch_completed)
        self.statusBar().showMessage(f"กำลังแปล: {self._batch_completed} / {self._batch_total}")

        if self._batch_completed >= self._batch_total:
            self.progress_bar.setVisible(False)
            self.btn_smart_trans.setEnabled(True)
            self.btn_opt_trans.setEnabled(True)
            self.btn_cinematic_menu.setEnabled(True)
            
            if self._batch_errors:
                QMessageBox.warning(self, "Batch Completed with Errors", f"แปลเสร็จสิ้น {self._batch_total - len(self._batch_errors)} รายการ (ผิดพลาด {len(self._batch_errors)} รายการ)")
            else:
                QMessageBox.information(self, "Batch Complete", f"แปลซับไตเติ้ลครบทั้ง {self._batch_total} รายการเรียบร้อยแล้ว!")

    def translate_options(self):
        if self.current_source_row < 0 or self.current_source_row >= len(self.model.entries):
            return
        entry = self.model.entries[self.current_source_row]
        if not entry.source.strip():
            return

        cfg = ConfigManager.load_config()
        self.btn_opt_trans.setEnabled(False)
        self.statusBar().showMessage(f"กำลังดึง 3 สไตล์คำแปลสำหรับ #{entry.idx}...")

        prompt = self._build_prompt(entry, "options")

        is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")
        worker = ApiWorker(CoreAI.generate_content, cfg, prompt, is_local=is_local)
        
        forwarder = ThreadSafeWorkerSignalsForwarder(
            on_success=lambda reply: self._on_options_success(reply),
            on_error=lambda err: self._on_single_error(err),
            parent=self
        )
        worker.signals.finished.connect(forwarder.handle_finished)
        worker.signals.error.connect(forwarder.handle_error)
        wid = id(worker)
        worker.signals.finished.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        worker.signals.error.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        self._workers[wid] = worker
        self.threadpool.start(worker)

    def _on_options_success(self, reply: str):
        self.btn_opt_trans.setEnabled(True)
        clean_reply = re.sub(r'^```[^\n]*\n?|\n?```$', '', reply.strip(), flags=re.MULTILINE)
        try:
            options = json.loads(clean_reply)
            if not isinstance(options, list) or len(options) == 0: raise ValueError()
        except Exception:
            QMessageBox.warning(self, "Parse Error", f"AI ส่งคำตอบในรูปแบบที่ไม่ถูกต้อง:\n{reply}")
            return

        dlg = TranslationOptionsDialog(self, options)
        if dlg.exec() and dlg.selected_text:
            choice = dlg.selected_text
            if self.chk_guide_mode.isChecked():
                self.model.update_ai_ref(self.current_source_row, choice)
                self.txt_ai.setPlainText(choice)
            else:
                self.model.update_trans(self.current_source_row, choice)
                self.txt_trans.setPlainText(choice)

    def translate_cinematic(self, mode_key: str):
        if self.current_source_row < 0 or self.current_source_row >= len(self.model.entries):
            return
        entry = self.model.entries[self.current_source_row]
        if not entry.source.strip():
            return

        cfg = ConfigManager.load_config()
        self.btn_cinematic_menu.setEnabled(False)
        self.statusBar().showMessage(f"กำลังแปลโทน '{mode_key}' สำหรับ #{entry.idx}...")

        prompt = self._build_prompt(entry, "cinematic", mode_key=mode_key)

        is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")
        worker = ApiWorker(CoreAI.generate_content, cfg, prompt, is_local=is_local)
        
        forwarder = ThreadSafeWorkerSignalsForwarder(
            on_success=lambda reply: self._on_cinematic_success(reply),
            on_error=lambda err: self._on_single_error(err),
            parent=self
        )
        worker.signals.finished.connect(forwarder.handle_finished)
        worker.signals.error.connect(forwarder.handle_error)
        wid = id(worker)
        worker.signals.finished.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        worker.signals.error.connect(lambda _, w_id=wid: self._workers.pop(w_id, None))
        self._workers[wid] = worker
        self.threadpool.start(worker)

    def _on_cinematic_success(self, reply: str):
        self.btn_cinematic_menu.setEnabled(True)
        translated = re.sub(r'^"|"$', '', reply.strip())
        if self.chk_guide_mode.isChecked():
            self.model.update_ai_ref(self.current_source_row, translated)
            self.txt_ai.setPlainText(translated)
        else:
            self.model.update_trans(self.current_source_row, translated)
            self.txt_trans.setPlainText(translated)
        self.statusBar().showMessage("แปลโทนภาพยนตร์สำเร็จ!", 3000)

    def autowrap_current_or_selection(self):
        def wrap_thai(text: str) -> str:
            text = text.replace('\r\n', '\n').strip()
            if '\n' in text or len(text) <= 35:
                return text
            mid = len(text) // 2
            best_split = -1
            min_dist = len(text)
            for i, ch in enumerate(text):
                if ch in [' ', ',', '!', '?', '-', ';']:
                    dist = abs(i - mid)
                    if dist < min_dist:
                        min_dist = dist
                        best_split = i

            if best_split > 10 and best_split < len(text) - 10:
                return text[:best_split].strip() + '\n' + text[best_split:].strip()
            return text

        selected = self.table.selectionModel().selectedRows()
        if not selected and self.current_source_row >= 0:
            selected_rows = [self.current_source_row]
        else:
            selected_rows = [self.proxy.mapToSource(idx).row() for idx in selected]

        for r in selected_rows:
            old_t = self.model.entries[r].trans
            if old_t:
                wrapped = wrap_thai(old_t)
                self.model.update_trans(r, wrapped)

        if self.current_source_row in selected_rows:
            self.txt_trans.setPlainText(self.model.entries[self.current_source_row].trans)

        self.statusBar().showMessage(f"จัดระเบียบและตัดคำ 2 บรรทัดสำหรับ {len(selected_rows)} รายการเรียบร้อย", 3000)

    def open_prompts_dialog(self):
        dlg = PromptSettingsDialog(self)
        dlg.profile_changed_signal.connect(self.on_dialog_profile_changed)
        if dlg.exec():
            self.refresh_main_profile_list()
            self.dock_glossary.load_glossary()

    def on_dialog_profile_changed(self, prof_name: str):
        self.refresh_main_profile_list()
        self.dock_glossary.load_glossary()

    def toggle_glossary_dock(self):
        if self.dock_glossary.isVisible():
            self.dock_glossary.hide()
        else:
            self.dock_glossary.show()
            self.dock_glossary.raise_()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        self._is_closing = True
        event.accept()

def main():
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("memolyviza.tsub.studio.1.0")
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    icon_path = os.path.join(CURRENT_DIR, "TSub.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    window = TSubApp()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()