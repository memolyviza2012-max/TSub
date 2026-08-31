# -*- coding: utf-8 -*-
"""
TSub Standalone - High-Performance Batch Translation Engine (TRun-Style)
High-speed bulk chunking, multi-threading, tag masking, auto-saving, and real-time logs.
"""

import os
import re
import time
import unicodedata
from typing import List, Dict, Tuple, Optional

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from srt_engine import SrtEntry, SrtEngine
from config_manager import ConfigManager
from core_ai import CoreAI

class BatchWorkerSignals(QObject):
    progress = pyqtSignal(int, int)          # current_done, total
    batch_progress = pyqtSignal(int, int)    # current_batch, total_batches
    log = pyqtSignal(str, str)               # message, hex_color
    finished = pyqtSignal()                  # normal finish
    stopped = pyqtSignal()                   # stopped by user
    error = pyqtSignal(str)                  # fatal error
    entry_updated = pyqtSignal(int, str)     # srt_index, translated_text

class SrtBatchWorker(QRunnable):
    _RE_THAI = re.compile(r'[\u0E00-\u0E7F]')
    _RE_TAG = re.compile(r'(<[^>]+>|\\n|\\r|\n|\r|%[sdiefg]|\{\d+\}|\[\[[^\]]+\]\])')
    _RE_TSV_LINE = re.compile(r'^"?(\d+)"?\t(.*)')
    _RE_CODE_FENCE_START = re.compile(r'^```[^\n]*\n?', re.MULTILINE)
    _RE_CODE_FENCE_END = re.compile(r'\n?```$', re.MULTILINE)

    def __init__(
        self,
        entries: List[SrtEntry],
        output_filepath: str,
        batch_size: int = 15,
        delay_ms: int = 200,
        threads: int = 2,
        skip_translated: bool = True,
        use_mask: bool = True,
        use_glossary: bool = True,
        max_retries: int = 3
    ):
        super().__init__()
        self.signals = BatchWorkerSignals()
        self.entries = entries
        self.output_filepath = output_filepath
        self.batch_size = max(1, batch_size)
        self.delay_ms = delay_ms
        self.threads = threads
        self.skip_translated = skip_translated
        self.use_mask = use_mask
        self.use_glossary = use_glossary
        self.max_retries = max_retries
        self._is_paused = False
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def is_thai(self, text: str) -> bool:
        if not text or not isinstance(text, str):
            return False
        return bool(self._RE_THAI.search(text))

    def mask_tags(self, text: str) -> Tuple[str, Dict[str, str]]:
        if not self.use_mask:
            return text, {}
        tags = self._RE_TAG.findall(text)
        masked_text = text
        placeholders = {}
        for idx, tag in enumerate(tags):
            placeholder = f"[TAG_{idx}]"
            if placeholder not in placeholders:
                placeholders[placeholder] = tag
            masked_text = masked_text.replace(tag, placeholder, 1)
        return masked_text, placeholders

    def unmask_tags(self, text: str, placeholders: Dict[str, str]) -> str:
        if not self.use_mask or not placeholders:
            return text
        unmasked = text
        for placeholder, original_tag in placeholders.items():
            unmasked = unmasked.replace(placeholder, original_tag)
        return unmasked

    def enforce_glossary(self, text: str, glossary: Dict[str, str]) -> str:
        if not self.use_glossary or not glossary:
            return text
        for wrong_word, correct_word in glossary.items():
            if correct_word:
                try:
                    text = re.sub(r'\b' + re.escape(str(wrong_word)) + r'\b', str(correct_word), text, flags=re.IGNORECASE)
                except Exception:
                    text = text.replace(str(wrong_word), str(correct_word))
        return text

    def build_batch_prompt(self, batch: List[Tuple[int, SrtEntry, Dict[str, str]]], cfg: dict, prof: dict) -> str:
        src_lang = prof.get("source_language", "English")
        tgt_lang = prof.get("target_language", "Thai")
        lore = prof.get("project_lore", "").strip()
        lore_section = f"\n[STORY & WORLD LORE CONTEXT]\n{lore}\n" if lore else ""

        # Dynamic glossary for this batch
        glossary = prof.get("glossary", {})
        matched_glos = []
        batch_combined_text = " ".join([e.source for _, e, _ in batch])
        for eng, th in glossary.items():
            if re.search(r'\b' + re.escape(eng) + r'\b', batch_combined_text, re.IGNORECASE):
                matched_glos.append(f"- {eng} -> {th}")
        
        glos_section = ""
        if matched_glos:
            glos_section = "\n[MANDATORY GLOSSARY - You MUST use these exact terms]:\n" + "\n".join(matched_glos) + "\n"

        lines_payload = []
        for idx, entry, _ in batch:
            clean_src = entry.source.replace('\n', ' [BR] ')
            masked_src, _ = self.mask_tags(clean_src)
            lines_payload.append(f"{entry.idx}\t{masked_src}")

        subtitles_payload = "\n".join(lines_payload)

        prompt = f"""You are a Master-Level Subtitle Translation Engine specialized in high-speed, fluent dialogue translation from {src_lang} to {tgt_lang}.

CRITICAL BATCH RULES:
1. Translate each line into natural, spoken {tgt_lang} dialogue suitable for cinematic subtitles (concise, max 2 lines).
2. Output format MUST be strict TSV: [Subtitle_Index]\\t[Thai_Translation]
3. Keep all placeholders like [TAG_0], [TAG_1] and [BR] (line break) intact.
4. Maintain exact line count ({len(batch)} lines). Do NOT merge or drop lines.
5. Return ONLY the raw TSV lines. No explanations, no markdown formatting.

{lore_section}{glos_section}
Subtitles to translate ({src_lang}):
{subtitles_payload}"""
        return prompt

    def parse_batch_response(self, response_text: str, batch: List[Tuple[int, SrtEntry, Dict[str, str]]]) -> Dict[int, str]:
        results = {}
        clean_text = self._RE_CODE_FENCE_START.sub('', response_text)
        clean_text = self._RE_CODE_FENCE_END.sub('', clean_text).strip()
        lines = clean_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                try:
                    idx = int(re.sub(r'\D', '', parts[0]))
                    trans = parts[1].strip().replace('[BR]', '\n')
                    results[idx] = trans
                except ValueError:
                    continue

        # Fallback: if TSV indices failed, match sequentially
        if len(results) < len(batch) // 2 and len(lines) == len(batch):
            for i, line in enumerate(lines):
                orig_idx = batch[i][1].idx
                results[orig_idx] = line.strip().replace('[BR]', '\n')

        return results

    @pyqtSlot()
    def run(self):
        try:
            cfg = ConfigManager.load_config()
            prof = ConfigManager.get_active_profile_data()
            glossary = prof.get("glossary", {})
            is_local = (cfg.get("provider", "") == "Local LLM" or cfg.get("model", "") == "custom-local-llm")

            # Filter items to translate
            todo_entries = []
            for i, e in enumerate(self.entries):
                if self.skip_translated and (e.trans.strip() or self.is_thai(e.trans)):
                    continue
                if not e.source.strip():
                    continue
                masked_src, placeholders = self.mask_tags(e.source)
                todo_entries.append((i, e, placeholders))

            total_todo = len(todo_entries)
            if total_todo == 0:
                self.signals.log.emit("✨ ทุกรายการได้รับการแปลเรียบร้อยแล้ว ไม่มีรายการที่ต้องแปลเพิ่ม", "#a6e3a1")
                self.signals.progress.emit(len(self.entries), len(self.entries))
                self.signals.finished.emit()
                return

            self.signals.log.emit(
                f"🚀 เริ่มการแปลแบบ Batch: ทั้งหมด {total_todo} รายการ (Batch Size: {self.batch_size}, Delay: {self.delay_ms}ms, Provider: {cfg.get('provider')})",
                "#89b4fa"
            )

            # Chunk into batches
            batches = [todo_entries[i:i + self.batch_size] for i in range(0, total_todo, self.batch_size)]
            total_batches = len(batches)
            completed_count = len(self.entries) - total_todo

            start_time = time.time()

            for b_idx, batch in enumerate(batches, start=1):
                if self._is_stopped:
                    self.signals.log.emit("⏹️ การแปลถูกยกเลิกโดยผู้ใช้", "#f38ba8")
                    self.signals.stopped.emit()
                    return

                while self._is_paused:
                    if self._is_stopped:
                        self.signals.stopped.emit()
                        return
                    time.sleep(0.3)

                b_start = time.time()
                prompt = self.build_batch_prompt(batch, cfg, prof)
                success = False

                for attempt in range(1, self.max_retries + 1):
                    if self._is_stopped: break
                    try:
                        reply = CoreAI.generate_content(cfg, prompt, is_local=is_local)
                        parsed = self.parse_batch_response(reply, batch)

                        if len(parsed) >= len(batch) * 0.7:  # At least 70% matched
                            for orig_i, entry, placeholders in batch:
                                if entry.idx in parsed:
                                    raw_th = parsed[entry.idx]
                                    unmasked_th = self.unmask_tags(raw_th, placeholders)
                                    final_th = self.enforce_glossary(unmasked_th, glossary)
                                    entry.trans = final_th
                                    completed_count += 1
                                    self.signals.entry_updated.emit(entry.idx, final_th)

                            success = True
                            b_dur = time.time() - b_start
                            self.signals.log.emit(
                                f"✅ Batch #{b_idx}/{total_batches} สำเร็จ ({len(batch)} รายการ ใน {b_dur:.1f}s)",
                                "#a6e3a1"
                            )
                            break
                        else:
                            raise Exception(f"Parsed {len(parsed)}/{len(batch)} items from model output.")
                    except Exception as ex:
                        self.signals.log.emit(
                            f"⚠️ Batch #{b_idx} ล้มเหลว (ครั้งที่ {attempt}/{self.max_retries}): {ex}",
                            "#fab387"
                        )
                        time.sleep(1.0 * attempt)

                if not success:
                    self.signals.log.emit(
                        f"❌ ข้าม Batch #{b_idx} เนื่องจากเกินโควตารีไทร",
                        "#f38ba8"
                    )

                # Save checkpoint to disk
                try:
                    SrtEngine.save_srt(self.output_filepath, self.entries, mode="trans_fallback_source")
                except Exception as e:
                    self.signals.log.emit(f"⚠️ บันทึก Checkpoint ล้มเหลว: {e}", "#f38ba8")

                self.signals.progress.emit(completed_count, len(self.entries))
                self.signals.batch_progress.emit(b_idx, total_batches)

                if self.delay_ms > 0 and b_idx < total_batches:
                    time.sleep(self.delay_ms / 1000.0)

            total_elapsed = time.time() - start_time
            self.signals.log.emit(
                f"🎉 การแปลเสร็จสิ้นสมบูรณ์! แปลสำเร็จ {completed_count}/{len(self.entries)} รายการ (ใช้เวลา {total_elapsed:.1f}s)",
                "#a6e3a1"
            )
            self.signals.finished.emit()

        except Exception as e:
            self.signals.log.emit(f"💥 เกิดข้อผิดพลาดร้ายแรง: {e}", "#f38ba8")
            self.signals.error.emit(str(e))