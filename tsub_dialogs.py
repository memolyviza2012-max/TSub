# -*- coding: utf-8 -*-
"""
TSub Standalone - Dialogs & UI Components
Settings, Profile Manager, Auto-Generator (Movies, Anime & Animation with Language Pair), Glossary Manager, and Style Options.
"""

import os
import json
import csv
import re
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QDockWidget, QAbstractItemView, QRadioButton, QButtonGroup, QScrollArea,
    QTabWidget, QTextEdit, QGroupBox, QApplication, QInputDialog
)
from PyQt6.QtCore import Qt, QLocale, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from config_manager import ConfigManager, DEFAULT_PROFILE_TEMPLATE
from core_ai import CoreAI, ApiWorker
from tsub_prompts import DEFAULT_SUBTITLE_PROMPT, DEFAULT_SUBTITLE_OPTIONS_PROMPT, CINEMATIC_MODES

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings (AI & API Models)")
        self.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.setFixedSize(480, 400)

        self.api_keys = {
            "OpenAI": "",
            "DeepSeek": "",
            "Google Gemini": "",
            "Anthropic Claude": ""
        }
        self.models_by_provider = {
            "OpenAI": [
                "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
                "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini",
                "o4-mini", "o3-mini", "o3", "o1", "gpt-3.5-turbo"
            ],
            "DeepSeek": ["deepseek-chat", "deepseek-reasoner"],
            "Google Gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash", "gemini-3.5-flash", "gemini-3.5-pro"],
            "Anthropic Claude": ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"],
            "Local LLM": ["custom-local-llm"]
        }
        self.current_provider = "OpenAI"

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cbo_provider = QComboBox()
        self.cbo_provider.addItems(["OpenAI", "DeepSeek", "Google Gemini", "Anthropic Claude", "Local LLM"])
        self.cbo_provider.currentTextChanged.connect(self.on_provider_changed)
        form.addRow("1. AI Provider:", self.cbo_provider)

        self.txt_api = QLineEdit()
        self.txt_api.setEchoMode(QLineEdit.EchoMode.Password)
        self.lbl_api = QLabel("2. API Key:")
        form.addRow(self.lbl_api, self.txt_api)

        self.cbo_model = QComboBox()
        self.cbo_model.setEditable(True)
        form.addRow("3. Model Name:", self.cbo_model)

        self.txt_base_url = QLineEdit()
        self.txt_base_url.setPlaceholderText("Optional (e.g. OpenRouter URL)")
        form.addRow("4. Base API URL:", self.txt_base_url)

        self.spn_temp = QDoubleSpinBox()
        self.spn_temp.setRange(0.0, 2.0)
        self.spn_temp.setSingleStep(0.1)
        form.addRow("5. Temperature:", self.spn_temp)

        self.spn_max_tokens = QSpinBox()
        self.spn_max_tokens.setRange(256, 128000)
        self.spn_max_tokens.setSingleStep(1024)
        form.addRow("6. Max Tokens:", self.spn_max_tokens)

        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(10, 600)
        self.spn_timeout.setSuffix(" sec")
        form.addRow("7. Timeout:", self.spn_timeout)

        layout.addLayout(form)
        layout.addStretch()

        btn_save = QPushButton("💾 Save Settings")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 8px 16px;")
        btn_save.clicked.connect(self.save_config)
        layout.addWidget(btn_save)

        self.load_config()

    def on_provider_changed(self, new_provider: str):
        if self.current_provider != "Local LLM":
            self.api_keys[self.current_provider] = self.txt_api.text().strip()

        self.current_provider = new_provider

        if new_provider == "Local LLM":
            self.txt_api.clear()
            self.txt_api.setEnabled(False)
            self.lbl_api.setText("API Key (Not needed):")
            self.txt_base_url.setPlaceholderText("http://localhost:1234/v1/chat/completions")
        else:
            self.txt_api.setEnabled(True)
            self.txt_api.setText(self.api_keys.get(new_provider, ""))
            self.lbl_api.setText(f"{new_provider} Key:")
            self.txt_base_url.setPlaceholderText("Optional (e.g. OpenRouter URL)")

        current_model = self.cbo_model.currentText()
        self.cbo_model.clear()
        models = self.models_by_provider.get(new_provider, [])
        self.cbo_model.addItems(models)
        if current_model in models:
            self.cbo_model.setCurrentText(current_model)

    def load_config(self):
        cfg = ConfigManager.load_config()
        self.api_keys["OpenAI"] = cfg.get("openai_key", "")
        self.api_keys["DeepSeek"] = cfg.get("deepseek_key", "")
        self.api_keys["Google Gemini"] = cfg.get("google_key", "")
        self.api_keys["Anthropic Claude"] = cfg.get("anthropic_key", "")

        provider = cfg.get("provider", "OpenAI")
        saved_model = cfg.get("model", "gpt-4o-mini")

        self.cbo_provider.blockSignals(True)
        self.cbo_provider.setCurrentText(provider)
        self.cbo_provider.blockSignals(False)

        self.on_provider_changed(provider)
        self.cbo_model.setCurrentText(saved_model)

        self.txt_base_url.setText(cfg.get("base_url", ""))
        self.spn_temp.setValue(float(cfg.get("temperature", 0.3)))
        self.spn_max_tokens.setValue(int(cfg.get("max_tokens", 4096)))
        self.spn_timeout.setValue(int(cfg.get("timeout", 60)))

        if provider != "Local LLM":
            self.txt_api.setText(self.api_keys.get(provider, ""))

    def save_config(self):
        if self.current_provider != "Local LLM":
            self.api_keys[self.current_provider] = self.txt_api.text().strip()

        cfg = ConfigManager.load_config()
        cfg["provider"] = self.cbo_provider.currentText()
        cfg["model"] = self.cbo_model.currentText().strip()
        cfg["openai_key"] = self.api_keys["OpenAI"]
        cfg["deepseek_key"] = self.api_keys["DeepSeek"]
        cfg["google_key"] = self.api_keys["Google Gemini"]
        cfg["anthropic_key"] = self.api_keys["Anthropic Claude"]
        cfg["base_url"] = self.txt_base_url.text().strip()
        cfg["temperature"] = self.spn_temp.value()
        cfg["max_tokens"] = self.spn_max_tokens.value()
        cfg["timeout"] = self.spn_timeout.value()

        ConfigManager.save_config(cfg)
        self.accept()
class PromptSettingsDialog(QDialog):
    profile_changed_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 Prompt Settings & Profiles (Movies, Anime & Animation)")
        self.resize(880, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Profile Management Header
        prof_bar = QHBoxLayout()
        prof_bar.addWidget(QLabel("📁 <b>Active Profile:</b>"))
        
        self.cbo_profile = QComboBox()
        self.cbo_profile.setMinimumWidth(160)
        self.cbo_profile.currentTextChanged.connect(self.on_profile_switched)
        prof_bar.addWidget(self.cbo_profile)

        btn_new_prof = QPushButton("➕ New")
        btn_new_prof.clicked.connect(self.new_profile)
        prof_bar.addWidget(btn_new_prof)

        btn_clone_prof = QPushButton("📋 Clone")
        btn_clone_prof.clicked.connect(self.clone_profile)
        prof_bar.addWidget(btn_clone_prof)

        btn_rename_prof = QPushButton("✏️ Rename")
        btn_rename_prof.clicked.connect(self.rename_profile)
        prof_bar.addWidget(btn_rename_prof)

        btn_del_prof = QPushButton("🗑️ Delete")
        btn_del_prof.clicked.connect(self.delete_profile)
        prof_bar.addWidget(btn_del_prof)

        prof_bar.addStretch()
        layout.addLayout(prof_bar)

        # 2. Auto-Generate Prompts for Movies & Animation GroupBox
        grp_auto = QGroupBox("✨ Auto-Generate Prompts for Movies, Anime & Animation (สร้าง Prompt อัจฉริยะ)")
        grp_auto.setStyleSheet("""
            QGroupBox {
                border: 1px solid #89b4fa;
                border-radius: 8px;
                margin-top: 8px;
                font-weight: bold;
                color: #89b4fa;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        auto_layout = QVBoxLayout(grp_auto)
        auto_layout.setSpacing(8)

        # Row 1: Title + Media Type + Source Lang + Target Lang
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("ชื่อเรื่อง/ผลงาน:"))
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("เช่น Oppenheimer, ดาบพิฆาตอสูร, Arcane, Spirited Away")
        r1.addWidget(self.txt_title, stretch=2)

        r1.addWidget(QLabel("ประเภทสื่อ:"))
        self.cbo_media_type = QComboBox()
        self.cbo_media_type.addItems([
            "🎬 ภาพยนตร์ (Live-Action Movie)",
            "🎌 อนิเมะ / มังงะ (Anime / Animation)",
            "📺 ซีรีส์ / ละคร (TV Series / Drama)",
            "🎭 แอนิเมชัน / การ์ตูน (3D / Western Animation)",
            "🎙️ สารคดี / เรียลลิตี้ (Documentary / Talk Show)",
            "🎮 คัตซีนเกม / วิดีโอเกม (Game Cutscenes)"
        ])
        r1.addWidget(self.cbo_media_type, stretch=1)

        r1.addWidget(QLabel("ต้นทาง:"))
        self.cbo_src_lang = QComboBox()
        self.cbo_src_lang.setEditable(True)
        self.cbo_src_lang.addItems(["English", "Japanese (ญี่ปุ่น)", "Chinese (จีน)", "Korean (เกาหลี)", "French (ฝรั่งเศส)", "German (เยอรมัน)", "Spanish (สเปน)"])
        r1.addWidget(self.cbo_src_lang, stretch=1)

        r1.addWidget(QLabel("ปลายทาง:"))
        self.cbo_tgt_lang = QComboBox()
        self.cbo_tgt_lang.setEditable(True)
        self.cbo_tgt_lang.addItems(["Thai (ไทย)", "English", "Japanese", "Chinese"])
        r1.addWidget(self.cbo_tgt_lang, stretch=1)
        auto_layout.addLayout(r1)

        # Row 2: Tone + Extra Rules + Generate Button
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("สไตล์บทสนทนา:"))
        self.cbo_tone_style = QComboBox()
        self.cbo_tone_style.addItems([
            "General / Natural (บทพูดธรรมชาติ ไหลลื่น)",
            "Action / Gritty (ดิบเถื่อน บู๊ล้างผลาญ สัจนิยม สบถสมจริง)",
            "Anime / Shonen (อนิเมะคลาสสิก ปลุกใจ สรรพนามเฉพาะตัว)",
            "Fantasy / Medieval (ย้อนยุค แฟนตาซี คำราชาศัพท์ ข้า-เจ้า-ท่าน)",
            "Sci-Fi / Cyberpunk (ไซไฟ โลกอนาคต เทคโนโลยีล้ำยุค)",
            "Comedy / Modern Slang (คอมเมดี้ มุกตลก สแลงวัยรุ่น กวนๆ)",
            "Romance / Melodrama (โรแมนติก ดราม่า ภาษาหวานละมุนหรือสะเทือนอารมณ์)",
            "Dark / Horror / Mystery (ระทึกขวัญ สยองขวัญ มืดมน ลึกลับ)",
            "Children / Family (เด็กและครอบครัว สุภาพ น่ารัก เข้าใจง่าย)"
        ])
        r2.addWidget(self.cbo_tone_style, stretch=2)

        r2.addWidget(QLabel("กฎเพิ่มเติม:"))
        self.txt_rules = QLineEdit()
        self.txt_rules.setPlaceholderText("เช่น ไม่ต้องแปลชื่อเฉพาะตัวละคร, รักษาคำลงท้ายญี่ปุ่น (-san, -kun), ตัวเอกผู้หญิงพูดห้าว")
        r2.addWidget(self.txt_rules, stretch=3)

        self.btn_auto_gen = QPushButton("✨ สร้างข้อมูลอัตโนมัติ")
        self.btn_auto_gen.setStyleSheet("""
            QPushButton {
                background-color: #f5c2e7;
                color: #11111b;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f38ba8;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #a6adc8;
            }
        """)
        self.btn_auto_gen.clicked.connect(self.run_auto_generate)
        r2.addWidget(self.btn_auto_gen, stretch=1)
        auto_layout.addLayout(r2)

        layout.addWidget(grp_auto)

        # 3. Tabs for Prompt Editing
        self.tabs = QTabWidget()

        # Tab 1: Main Subtitle Prompt
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.setContentsMargins(8, 8, 8, 8)
        info1 = QLabel("💡 ตัวแปรที่ระบบจะแทนที่อัตโนมัติ: {id} = รหัสซับ, {duration} = วินาที, {source_text} = ข้อความต้นฉบับ, [GLOSSARY TO USE] = ตำแหน่งแทรกคำศัพท์, {lore} = ข้อมูลโลก/บริบท")
        info1.setStyleSheet("color: #fab387; font-weight: 500;")
        info1.setWordWrap(True)
        l1.addWidget(info1)

        self.txt_main_prompt = QTextEdit()
        self.txt_main_prompt.setFont(QFont("Consolas", 10))
        l1.addWidget(self.txt_main_prompt)
        self.tabs.addTab(t1, "⚡ แปลหลัก (Main Prompt)")

        # Tab 2: 3-Options Prompt
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        l2.setContentsMargins(8, 8, 8, 8)
        info2 = QLabel("💡 Prompt สำหรับเมนู 'แปล 3 สไตล์' (F3) บังคับคืนค่าเป็น JSON Array ของ 3 คำตอบ")
        info2.setStyleSheet("color: #a6e3a1; font-weight: 500;")
        l2.addWidget(info2)

        self.txt_options_prompt = QTextEdit()
        self.txt_options_prompt.setFont(QFont("Consolas", 10))
        l2.addWidget(self.txt_options_prompt)
        self.tabs.addTab(t2, "🎭 แปล 3 สไตล์ (Options Prompt)")

        # Tab 3: Cinematic Tones
        t3 = QWidget()
        l3 = QVBoxLayout(t3)
        l3.setContentsMargins(8, 8, 8, 8)

        tone_select_layout = QHBoxLayout()
        tone_select_layout.addWidget(QLabel("เลือกโทนที่ต้องการแก้ไข:"))
        self.cbo_tone = QComboBox()
        self.tone_keys = [
            ("natural", "บทพูดธรรมชาติ (Natural Dialogue)"),
            ("gritty", "ดิบเถื่อน / สัจนิยม (Gritty Action)"),
            ("fantasy", "ย้อนยุค / แฟนตาซี (Fantasy Archaic)"),
            ("casual_slang", "สแลง / วัยรุ่น (Casual Slang)"),
            ("formal", "สุภาพ / ทางการ (Formal)"),
            ("poem", "กลอน / บทกวี (Poetic Verse)"),
            ("robotic", "ประกาศระบบ / หุ่นยนต์ (Robotic AI)")
        ]
        for key, name in self.tone_keys:
            self.cbo_tone.addItem(name, key)
        self.cbo_tone.currentIndexChanged.connect(self.on_tone_selected)
        tone_select_layout.addWidget(self.cbo_tone, stretch=1)
        l3.addLayout(tone_select_layout)

        self.txt_tone_desc = QTextEdit()
        self.txt_tone_desc.setFont(QFont("Consolas", 10))
        self.txt_tone_desc.textChanged.connect(self.on_tone_text_changed)
        l3.addWidget(self.txt_tone_desc)
        self.tabs.addTab(t3, "🎬 โทนภาพยนตร์ (Cinematic Tones)")

        # Tab 4: Lore & World Context
        t4 = QWidget()
        l4 = QVBoxLayout(t4)
        l4.setContentsMargins(8, 8, 8, 8)

        info4 = QLabel("📖 ข้อมูลโลกและเนื้อเรื่อง (Lore / Background Context):\nสรุปเรื่องย่อ, บุคลิก/เพศของตัวละคร, ความสัมพันธ์ และคำศัพท์เฉพาะของภาพยนตร์/อนิเมะเรื่องนี้ เพื่อให้ AI แปลได้ตรงบริบทที่สุด")
        info4.setStyleSheet("color: #89b4fa; font-weight: 500;")
        info4.setWordWrap(True)
        l4.addWidget(info4)

        self.txt_lore = QTextEdit()
        self.txt_lore.setPlaceholderText("ตัวอย่าง:\n- ตัวเอกเป็นทหารรับจ้างหญิงชื่อ 'วาลีเรีย' พูดจาห้าวหาญแต่สุภาพกับผู้บังคับบัญชา\n- โลกของเรื่องเป็นไซเบอร์พังก์ดิสโทเปีย\n- ศัพท์ 'The Core' หมายถึง 'เตาปฏิกรณ์พลังงานหลักของนคร'")
        self.txt_lore.setFont(QFont("Segoe UI", 10))
        l4.addWidget(self.txt_lore)
        self.tabs.addTab(t4, "📖 ข้อมูลโลก & เนื้อเรื่อง (Lore Context)")

        layout.addWidget(self.tabs)

        # 4. Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("🔄 คืนค่าเริ่มต้น (Reset Defaults)")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("ยกเลิก")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 บันทึก Profile นี้")
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 8px 16px;")
        btn_save.clicked.connect(self.save_current_profile_data)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        self.cinematic_modes_data = {}
        self.current_tone_key = "natural"
        self.refresh_profile_list()

    def refresh_profile_list(self):
        profiles = ConfigManager.get_profile_list()
        active = ConfigManager.get_active_profile_name()
        self.cbo_profile.blockSignals(True)
        self.cbo_profile.clear()
        self.cbo_profile.addItems(profiles)
        if active in profiles:
            self.cbo_profile.setCurrentText(active)
        self.cbo_profile.blockSignals(False)
        self.load_active_profile_to_ui()

    def on_profile_switched(self, prof_name: str):
        if not prof_name: return
        ConfigManager.set_active_profile_name(prof_name)
        self.load_active_profile_to_ui()
        self.profile_changed_signal.emit(prof_name)

    def load_active_profile_to_ui(self):
        prof = ConfigManager.get_active_profile_data()
        self.txt_title.setText(prof.get("media_title", ""))
        self.cbo_media_type.setCurrentText(prof.get("media_type", "🎬 ภาพยนตร์ (Live-Action Movie)"))
        self.cbo_src_lang.setCurrentText(prof.get("source_language", "English"))
        self.cbo_tgt_lang.setCurrentText(prof.get("target_language", "Thai"))
        self.txt_main_prompt.setPlainText(prof.get("main_prompt", DEFAULT_SUBTITLE_PROMPT))
        self.txt_options_prompt.setPlainText(prof.get("options_prompt", DEFAULT_SUBTITLE_OPTIONS_PROMPT))
        self.txt_lore.setPlainText(prof.get("project_lore", ""))
        self.cinematic_modes_data = prof.get("cinematic_modes", CINEMATIC_MODES.copy())
        self.on_tone_selected(self.cbo_tone.currentIndex())

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "กรอกชื่อโปรไฟล์ใหม่ (เช่น ชื่อภาพยนตร์ / ซีรีส์):")
        if ok and name.strip():
            name = name.strip()
            if name in ConfigManager.get_profile_list():
                QMessageBox.warning(self, "Duplicate", "ชื่อโปรไฟล์นี้มีอยู่แล้ว!")
                return
            ConfigManager.create_profile(name)
            self.refresh_profile_list()

    def clone_profile(self):
        cur = self.cbo_profile.currentText()
        name, ok = QInputDialog.getText(self, "Clone Profile", f"คัดลอกโปรไฟล์ '{cur}' เป็นชื่อใหม่:")
        if ok and name.strip():
            name = name.strip()
            if name in ConfigManager.get_profile_list():
                QMessageBox.warning(self, "Duplicate", "ชื่อโปรไฟล์นี้มีอยู่แล้ว!")
                return
            ConfigManager.create_profile(name, copy_from=cur)
            self.refresh_profile_list()

    def rename_profile(self):
        cur = self.cbo_profile.currentText()
        name, ok = QInputDialog.getText(self, "Rename Profile", f"เปลี่ยนชื่อโปรไฟล์ '{cur}' เป็น:", text=cur)
        if ok and name.strip() and name.strip() != cur:
            name = name.strip()
            if name in ConfigManager.get_profile_list():
                QMessageBox.warning(self, "Duplicate", "ชื่อโปรไฟล์นี้มีอยู่แล้ว!")
                return
            ConfigManager.rename_profile(cur, name)
            self.refresh_profile_list()

    def delete_profile(self):
        cur = self.cbo_profile.currentText()
        if len(ConfigManager.get_profile_list()) <= 1:
            QMessageBox.warning(self, "Warning", "ไม่สามารถลบโปรไฟล์สุดท้ายได้!")
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"ต้องการลบโปรไฟล์ '{cur}' หรือไม่?")
        if reply == QMessageBox.StandardButton.Yes:
            ConfigManager.delete_profile(cur)
            self.refresh_profile_list()

    def on_tone_selected(self, idx: int):
        if idx < 0 or idx >= len(self.tone_keys):
            return
        key = self.tone_keys[idx][0]
        self.current_tone_key = key
        desc = self.cinematic_modes_data.get(key, CINEMATIC_MODES.get(key, ""))
        self.txt_tone_desc.blockSignals(True)
        self.txt_tone_desc.setPlainText(desc)
        self.txt_tone_desc.blockSignals(False)

    def on_tone_text_changed(self):
        if self.current_tone_key:
            self.cinematic_modes_data[self.current_tone_key] = self.txt_tone_desc.toPlainText().strip()

    def run_auto_generate(self):
        title = self.txt_title.text().strip()
        if not title:
            QMessageBox.warning(self, "ระบุชื่อเรื่อง", "กรุณากรอกชื่อภาพยนตร์, อนิเมะ, หรือซีรีส์ก่อนกดสร้างข้อมูล!")
            return

        media_type = self.cbo_media_type.currentText().strip()
        src_lang = self.cbo_src_lang.currentText().strip()
        tgt_lang = self.cbo_tgt_lang.currentText().strip()
        tone_style = self.cbo_tone_style.currentText().strip()
        rules = self.txt_rules.text().strip()

        cfg = ConfigManager.load_config()
        self.btn_auto_gen.setEnabled(False)
        self.btn_auto_gen.setText("⏳ กำลังสร้างข้อมูล...")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

        gen_prompt = f"""You are a World-Class Subtitle Localization Director and Master Prompt Engineer specialized in Cinematic Movies, Japanese Anime, Western Animation, and TV Series.

Target Media Title: '{title}'
Media Type: {media_type}
Language Pair: Translate from {src_lang} into {tgt_lang}
Dialogue & Tone Style: {tone_style}
Additional Translation Rules: '{rules if rules else "None"}'

Your task is to generate 3 tailored assets for translating subtitles for '{title}' from {src_lang} into {tgt_lang}:
1. 'main_prompt': A highly refined System Prompt for single-line subtitle translation from {src_lang} to {tgt_lang}.
   - MUST contain the literal tags: '{{id}}', '{{duration}}', '{{source_text}}', '{{lore}}', and '[GLOSSARY TO USE]'.
   - Direct the AI to translate into natural, spoken {tgt_lang} dialog tailored specifically to the tone, characters, and style of '{title}'. Max 2 lines. Preserve HTML tags.
   - For Japanese/Anime: Add rules for Japanese honorifics, speaking styles, and persona pronouns.
2. 'options_prompt': A System Prompt for 3-style subtitle translation (F3).
   - MUST instruct the AI to return a JSON array of 3 distinct {tgt_lang} subtitle options: ["Option 1", "Option 2", "Option 3"].
   - MUST contain: '{{id}}', '{{duration}}', '{{source_text}}', and '[GLOSSARY TO USE]'.
3. 'project_lore': A concise summary (in {tgt_lang}) of '{title}' covering:
   - Brief Story Background / Setting
   - Key Characters, their personalities, gender, and speaking pronouns (e.g. ฉัน/นาย, ข้า/เจ้า, พี่/น้อง)
   - Important Lore Terms or Signature Catchphrases

Return ONLY a valid JSON object with the following exact keys:
{{
  "main_prompt": "string",
  "options_prompt": "string",
  "project_lore": "string"
}}"""

        is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")

        def task():
            return CoreAI.generate_content(cfg, gen_prompt, is_local=is_local)

        def on_success(res_text: str):
            QApplication.restoreOverrideCursor()
            self.btn_auto_gen.setEnabled(True)
            self.btn_auto_gen.setText("✨ สร้างข้อมูลอัตโนมัติ")

            clean = re.sub(r'^```[^\n]*\n?|\n?```$', '', res_text.strip(), flags=re.MULTILINE)
            try:
                data = json.loads(clean)
                if "main_prompt" in data:
                    self.txt_main_prompt.setPlainText(data["main_prompt"].strip())
                if "options_prompt" in data:
                    self.txt_options_prompt.setPlainText(data["options_prompt"].strip())
                if "project_lore" in data:
                    self.txt_lore.setPlainText(data["project_lore"].strip())

                QMessageBox.information(
                    self, "สร้าง Prompt สำเร็จ!",
                    f"ระบบได้สร้าง Subtitle Prompts ({src_lang} -> {tgt_lang}) และ Lore Context สำหรับ '{title}' เรียบร้อยแล้ว!\n(อย่าลืมกด '💾 บันทึก Profile นี้' ด้านล่างเพื่อใช้งาน)"
                )
            except Exception as e:
                QMessageBox.warning(self, "Parse Error", f"ไม่สามารถแปลงข้อมูลที่ AI ส่งกลับมาได้:\n{e}\n\nข้อความดิบ:\n{res_text}")

        def on_error(err: str):
            QApplication.restoreOverrideCursor()
            self.btn_auto_gen.setEnabled(True)
            self.btn_auto_gen.setText("✨ สร้างข้อมูลอัตโนมัติ")
            QMessageBox.critical(self, "Error", f"เกิดข้อผิดพลาดในการสร้าง Prompt:\n{err}")

        worker = ApiWorker(task)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "ต้องการรีเซ็ตข้อความ Prompt ทั้งหมดกลับเป็นค่าเริ่มต้นหรือไม่?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.txt_main_prompt.setPlainText(DEFAULT_SUBTITLE_PROMPT)
            self.txt_options_prompt.setPlainText(DEFAULT_SUBTITLE_OPTIONS_PROMPT)
            self.txt_lore.setPlainText("")
            self.cinematic_modes_data = CINEMATIC_MODES.copy()
            self.on_tone_selected(self.cbo_tone.currentIndex())
            QMessageBox.information(self, "Reset Complete", "คืนค่า Prompt เริ่มต้นเรียบร้อยแล้ว (กดบันทึกเพื่อยืนยัน)")

    def save_current_profile_data(self):
        prof = ConfigManager.get_active_profile_data()
        prof["media_title"] = self.txt_title.text().strip()
        prof["media_type"] = self.cbo_media_type.currentText().strip()
        prof["source_language"] = self.cbo_src_lang.currentText().strip()
        prof["target_language"] = self.cbo_tgt_lang.currentText().strip()
        prof["main_prompt"] = self.txt_main_prompt.toPlainText().strip()
        prof["options_prompt"] = self.txt_options_prompt.toPlainText().strip()
        prof["project_lore"] = self.txt_lore.toPlainText().strip()
        prof["cinematic_modes"] = self.cinematic_modes_data

        ConfigManager.save_active_profile_data(prof)
        QMessageBox.information(self, "Saved", f"บันทึกข้อมูล Profile '{ConfigManager.get_active_profile_name()}' เรียบร้อยแล้ว!")
        self.accept()
class GlossaryDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("📚 Glossary Manager", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 ค้นหาคำศัพท์...")
        self.txt_search.textChanged.connect(self.filter_glossary)
        layout.addWidget(self.txt_search)

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Source Term (ต้นทาง)", "Target Term (คำแปล)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Input row
        inp_layout = QHBoxLayout()
        self.txt_eng = QLineEdit()
        self.txt_eng.setPlaceholderText("คำต้นฉบับ...")
        self.txt_thai = QLineEdit()
        self.txt_thai.setPlaceholderText("คำแปล...")
        btn_add = QPushButton("➕ เพิ่ม")
        btn_add.clicked.connect(self.add_term)
        inp_layout.addWidget(self.txt_eng)
        inp_layout.addWidget(self.txt_thai)
        inp_layout.addWidget(btn_add)
        layout.addLayout(inp_layout)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_del = QPushButton("🗑️ ลบที่เลือก")
        btn_del.clicked.connect(self.delete_selected)
        btn_import = QPushButton("📥 Import")
        btn_import.clicked.connect(self.import_glossary)
        btn_export = QPushButton("📤 Export")
        btn_export.clicked.connect(self.export_glossary)
        btn_save = QPushButton("💾 บันทึก")
        btn_save.clicked.connect(self.save_glossary)

        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        self.setWidget(container)
        self.load_glossary()

    def load_glossary(self):
        glossary = ConfigManager.load_glossary()
        self.table.setRowCount(0)
        for eng, th in glossary.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(eng))
            self.table.setItem(r, 1, QTableWidgetItem(th))

    def save_glossary(self):
        data = {}
        for r in range(self.table.rowCount()):
            eng_item = self.table.item(r, 0)
            th_item = self.table.item(r, 1)
            if eng_item and th_item:
                eng = eng_item.text().strip()
                th = th_item.text().strip()
                if eng:
                    data[eng] = th
        ConfigManager.save_glossary(data)
        QMessageBox.information(self, "Glossary Saved", f"บันทึกคำศัพท์ {len(data)} รายการลง Profile ปัจจุบันเรียบร้อย")

    def add_term(self):
        eng = self.txt_eng.text().strip()
        th = self.txt_thai.text().strip()
        if not eng:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(eng))
        self.table.setItem(r, 1, QTableWidgetItem(th))
        self.txt_eng.clear()
        self.txt_thai.clear()
        self.save_glossary()

    def delete_selected(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self.save_glossary()

    def filter_glossary(self, text: str):
        text = text.lower()
        for r in range(self.table.rowCount()):
            eng = self.table.item(r, 0).text().lower() if self.table.item(r, 0) else ""
            th = self.table.item(r, 1).text().lower() if self.table.item(r, 1) else ""
            self.table.setRowHidden(r, text not in eng and text not in th)

    def import_glossary(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Glossary", "", "Glossary Files (*.json *.csv);;All Files (*.*)")
        if not path:
            return
        data = ConfigManager.load_glossary()
        if path.endswith(".csv"):
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2 and row[0].strip():
                        data[row[0].strip()] = row[1].strip()
        else:
            with open(path, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        ConfigManager.save_glossary(data)
        self.load_glossary()
        QMessageBox.information(self, "Imported", "นำเข้าคำศัพท์เรียบร้อยแล้ว")

    def export_glossary(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Glossary", "tsub_glossary.json", "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        data = {}
        for r in range(self.table.rowCount()):
            eng = self.table.item(r, 0).text().strip()
            th = self.table.item(r, 1).text().strip()
            if eng:
                data[eng] = th

        if path.endswith(".csv"):
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Source Term", "Target Term"])
                for k, v in data.items():
                    writer.writerow([k, v])
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Exported", f"ส่งออกคำศัพท์ {len(data)} รายการเรียบร้อยแล้ว")


class TranslationOptionsDialog(QDialog):
    def __init__(self, parent=None, options: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("🎭 เลือกสไตล์คำแปล (Translation Options)")
        self.resize(550, 360)
        self.selected_text = ""
        self.options = options or []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl = QLabel("เลือกสไตล์คำแปลที่เหมาะสมที่สุดสำหรับฉากนี้:")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #89b4fa;")
        layout.addWidget(lbl)

        self.btn_group = QButtonGroup(self)
        self.radio_buttons = []

        labels = [
            "1. บทพูดธรรมชาติ (Natural / Conversational)",
            "2. แปลตรงตัว (Direct / Accurate)",
            "3. กระชับ คมคาย (Dynamic / Punchy)"
        ]

        for i, opt in enumerate(self.options):
            box = QWidget()
            box.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px; padding: 6px;")
            b_lay = QVBoxLayout(box)

            tag = labels[i] if i < len(labels) else f"สไตล์ที่ {i+1}"
            rb = QRadioButton(tag)
            rb.setStyleSheet("font-weight: bold; color: #a6e3a1;")
            if i == 0:
                rb.setChecked(True)
            self.btn_group.addButton(rb, i)
            self.radio_buttons.append((rb, opt))
            b_lay.addWidget(rb)

            txt = QLabel(opt)
            txt.setWordWrap(True)
            txt.setStyleSheet("color: #cdd6f4; font-size: 14px; padding-left: 20px;")
            b_lay.addWidget(txt)

            layout.addWidget(box)

        layout.addStretch()

        btns = QHBoxLayout()
        btn_apply = QPushButton("✅ ใช้คำแปลนี้ (Enter)")
        btn_apply.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 8px 16px;")
        btn_apply.clicked.connect(self.on_apply)
        btn_cancel = QPushButton("ยกเลิก")
        btn_cancel.clicked.connect(self.reject)

        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_apply)
        layout.addLayout(btns)

    def on_apply(self):
        idx = self.btn_group.checkedId()
        if 0 <= idx < len(self.options):
            self.selected_text = self.options[idx]
        self.accept()