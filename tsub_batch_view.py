# -*- coding: utf-8 -*-
"""
TSub Standalone - Batch Translation Pipeline View (TRun-Style)
High-throughput subtitle translator designed for massive SRT files.
"""

import os
import time
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

from srt_engine import SrtEngine, SrtEntry
from config_manager import ConfigManager
from tsub_batch_engine import SrtBatchWorker

class BatchTranslationView(QWidget):
    subtitles_updated = pyqtSignal(list)  # Emits updated entries when batch finishes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool.globalInstance()
        self.worker: Optional[SrtBatchWorker] = None
        self.entries: List[SrtEntry] = []
        self.input_file = ""
        self.output_file = ""
        self.start_time = 0.0

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ── 1. File Selection Group ───────────────────────────────────────────
        grp_files = QGroupBox("📂 Subtitle Files (ไฟล์คำบรรยาย)")
        grp_files.setStyleSheet("QGroupBox { font-weight: bold; color: #89b4fa; }")
        f_lay = QGridLayout(grp_files)
        f_lay.setSpacing(8)

        f_lay.addWidget(QLabel("Input .SRT:"), 0, 0)
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("เลือกไฟล์ .srt ต้นฉบับที่ต้องการแปล...")
        f_lay.addWidget(self.txt_input, 0, 1)
        btn_browse_in = QPushButton("Browse...")
        btn_browse_in.clicked.connect(self.browse_input)
        f_lay.addWidget(btn_browse_in, 0, 2)

        f_lay.addWidget(QLabel("Output .SRT:"), 1, 0)
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("ไฟล์ .srt ปลายทางที่จะบันทึกผลการแปล...")
        f_lay.addWidget(self.txt_output, 1, 1)
        btn_browse_out = QPushButton("Browse...")
        btn_browse_out.clicked.connect(self.browse_output)
        f_lay.addWidget(btn_browse_out, 1, 2)

        layout.addWidget(grp_files)

        # ── 2. Batch Engine Configuration ─────────────────────────────────────
        grp_cfg = QGroupBox("⚡ TRun Batch Engine Options (การตั้งค่าความเร็วและการแปลง)")
        grp_cfg.setStyleSheet("QGroupBox { font-weight: bold; color: #a6e3a1; }")
        c_lay = QGridLayout(grp_cfg)
        c_lay.setSpacing(8)

        c_lay.addWidget(QLabel("Batch Size (ขนาดชุด):"), 0, 0)
        self.spn_batch_size = QSpinBox()
        self.spn_batch_size.setRange(1, 100)
        self.spn_batch_size.setValue(20)
        self.spn_batch_size.setToolTip("จำนวนบรรทัดที่รวมส่งไปแปลใน 1 ครั้ง (แนะนำ: 15-30)")
        c_lay.addWidget(self.spn_batch_size, 0, 1)

        c_lay.addWidget(QLabel("Delay (หน่วงเวลา):"), 0, 2)
        self.spn_delay = QSpinBox()
        self.spn_delay.setRange(0, 5000)
        self.spn_delay.setSingleStep(100)
        self.spn_delay.setValue(200)
        self.spn_delay.setSuffix(" ms")
        self.spn_delay.setToolTip("ระยะเวลาหน่วงระหว่าง Batch เพื่อป้องกัน API Rate Limit")
        c_lay.addWidget(self.spn_delay, 0, 3)

        c_lay.addWidget(QLabel("Max Retries:"), 0, 4)
        self.spn_retries = QSpinBox()
        self.spn_retries.setRange(1, 10)
        self.spn_retries.setValue(3)
        c_lay.addWidget(self.spn_retries, 0, 5)

        # Checkboxes row
        chk_layout = QHBoxLayout()
        self.chk_skip = QCheckBox("ข้ามบรรทัดที่แปลแล้ว (Skip Translated)")
        self.chk_skip.setChecked(True)
        chk_layout.addWidget(self.chk_skip)

        self.chk_mask = QCheckBox("ป้องกัน Formatting Tags (Tag Masking)")
        self.chk_mask.setChecked(True)
        chk_layout.addWidget(self.chk_mask)

        self.chk_glossary = QCheckBox("บังคับใช้ Glossary (Enforce Glossary)")
        self.chk_glossary.setChecked(True)
        chk_layout.addWidget(self.chk_glossary)

        chk_layout.addStretch()
        c_lay.addLayout(chk_layout, 1, 0, 1, 6)

        layout.addWidget(grp_cfg)

        # ── 3. Controls & Action Buttons ──────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_start = QPushButton("🚀 START BATCH TRANSLATION (เริ่มการแปล)")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #11111b;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #94e2d5; }
            QPushButton:disabled { background-color: #313244; color: #585b70; }
        """)
        self.btn_start.clicked.connect(self.start_batch)
        btn_bar.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause)
        btn_bar.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹️ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_batch)
        btn_bar.addWidget(self.btn_stop)

        btn_bar.addStretch()

        self.btn_clear_log = QPushButton("🧹 ล้าง Log")
        self.btn_clear_log.clicked.connect(lambda: self.txt_log.clear())
        btn_bar.addWidget(self.btn_clear_log)

        layout.addLayout(btn_bar)

        # ── 4. Progress and Real-Time Stats ───────────────────────────────────
        stat_box = QFrame()
        stat_box.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px; padding: 6px;")
        stat_lay = QVBoxLayout(stat_box)
        stat_lay.setSpacing(4)

        prog_header = QHBoxLayout()
        self.lbl_prog_title = QLabel("ความคืบหน้าภาพรวม (Overall Progress):")
        self.lbl_prog_title.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        prog_header.addWidget(self.lbl_prog_title)
        prog_header.addStretch()
        self.lbl_stats = QLabel("⚡ ความเร็ว: 0 subs/s | ⏱️ ใช้เวลา: 00:00 | ⏳ คาดการณ์: 00:00")
        self.lbl_stats.setStyleSheet("font-weight: bold; color: #fab387;")
        prog_header.addWidget(self.lbl_stats)
        stat_lay.addLayout(prog_header)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(20)
        self.prog_bar.setValue(0)
        stat_lay.addWidget(self.prog_bar)

        layout.addWidget(stat_box)

        # ── 5. Live Console Log Monitor ───────────────────────────────────────
        l_header = QLabel("📟 Live Translation Console (รายงานการทำงานแบบเรียลไทม์):")
        l_header.setStyleSheet("font-weight: bold; color: #cba6f7;")
        layout.addWidget(l_header)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Consolas", 10))
        self.txt_log.setStyleSheet("background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px;")
        layout.addWidget(self.txt_log, stretch=1)

    # ── File Browse ───────────────────────────────────────────────────────────
    def set_active_file(self, filepath: str, entries: List[SrtEntry]):
        if filepath:
            self.input_file = filepath
            self.txt_input.setText(filepath)
            base, ext = os.path.splitext(filepath)
            self.output_file = f"{base}_translated.srt"
            self.txt_output.setText(self.output_file)
            self.entries = entries
            self.prog_bar.setMaximum(len(entries))
            self.prog_bar.setValue(0)
            self.log_message(f"📂 โหลดไฟล์จาก Studio: {os.path.basename(filepath)} ({len(entries)} ซับไตเติ้ล)", "#89b4fa")

    def browse_input(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Input SRT", "", "SubRip Subtitle (*.srt);;All Files (*.*)")
        if f:
            self.txt_input.setText(f)
            self.input_file = f
            base, _ = os.path.splitext(f)
            self.output_file = f"{base}_translated.srt"
            self.txt_output.setText(self.output_file)
            try:
                entries, enc = SrtEngine.load_srt(f)
                self.entries = entries
                self.prog_bar.setMaximum(len(entries))
                self.log_message(f"📂 โหลดไฟล์สำเร็จ: {os.path.basename(f)} ({len(entries)} ซับไตเติ้ล | Encoding: {enc})", "#89b4fa")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"ไม่สามารถอ่านไฟล์ .srt ได้:\n{e}")

    def browse_output(self):
        f, _ = QFileDialog.getSaveFileName(self, "Select Output SRT", self.output_file, "SubRip Subtitle (*.srt);;All Files (*.*)")
        if f:
            self.txt_output.setText(f)
            self.output_file = f

    # ── Batch Execution Controls ──────────────────────────────────────────────
    def log_message(self, text: str, color: str = "#cdd6f4"):
        timestamp = time.strftime("[%H:%M:%S] ")
        html = f'<span style="color: #6c7086;">{timestamp}</span><span style="color: {color};">{text}</span>'
        self.txt_log.append(html)
        self.txt_log.moveCursor(QTextCursor.MoveOperation.End)

    def start_batch(self):
        if not self.entries:
            if not self.input_file and self.txt_input.text().strip():
                self.browse_input()
            if not self.entries:
                QMessageBox.warning(self, "Warning", "กรุณาเลือกไฟล์ .srt ที่ต้องการแปลก่อน!")
                return

        out_path = self.txt_output.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Warning", "กรุณาระบุไฟล์ปลายทางที่จะบันทึก!")
            return
        self.output_file = out_path

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setText("⏸️ Pause")

        self.start_time = time.time()
        self.prog_bar.setMaximum(len(self.entries))
        self.prog_bar.setValue(0)

        self.worker = SrtBatchWorker(
            entries=self.entries,
            output_filepath=self.output_file,
            batch_size=self.spn_batch_size.value(),
            delay_ms=self.spn_delay.value(),
            skip_translated=self.chk_skip.isChecked(),
            use_mask=self.chk_mask.isChecked(),
            use_glossary=self.chk_glossary.isChecked(),
            max_retries=self.spn_retries.value()
        )

        self.worker.signals.log.connect(self.log_message)
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.finished.connect(self.on_finished)
        self.worker.signals.stopped.connect(self.on_stopped)
        self.worker.signals.error.connect(self.on_error)

        self.threadpool.start(self.worker)

    def toggle_pause(self):
        if not self.worker: return
        if self.worker._is_paused:
            self.worker.resume()
            self.btn_pause.setText("⏸️ Pause")
            self.log_message("▶️ ดำเนินการแปลต่อ...", "#89b4fa")
        else:
            self.worker.pause()
            self.btn_pause.setText("▶️ Resume")
            self.log_message("⏸️ พักการแปลชั่วคราว", "#fab387")

    def stop_batch(self):
        if self.worker:
            self.worker.stop()
            self.log_message("⏹️ กำลังส่งสัญญาณหยุดการทำงาน...", "#f38ba8")

    def on_progress(self, current: int, total: int):
        self.prog_bar.setValue(current)
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        rate = current / max(0.1, elapsed)
        remain_items = total - current
        remain_secs = int(remain_items / max(0.1, rate)) if rate > 0 else 0
        r_mins, r_secs = divmod(remain_secs, 60)
        eta_str = f"{r_mins:02d}:{r_secs:02d}"

        self.lbl_stats.setText(f"⚡ ความเร็ว: {rate:.1f} subs/s | ⏱️ ใช้เวลา: {time_str} | ⏳ คาดการณ์: {eta_str}")
        self.lbl_prog_title.setText(f"ความคืบหน้า: {current:,} / {total:,} ({current*100//max(1, total)}%)")

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.subtitles_updated.emit(self.entries)
        QMessageBox.information(self, "Success", f"แปลแบบ Batch เสร็จสิ้นสมบูรณ์!\nไฟล์ถูกบันทึกไว้ที่:\n{self.output_file}")

    def on_stopped(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.subtitles_updated.emit(self.entries)

    def on_error(self, err: str):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "Batch Error", f"เกิดข้อผิดพลาดในการแปล:\n{err}")