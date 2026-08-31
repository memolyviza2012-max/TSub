# -*- coding: utf-8 -*-
"""
TSub - Subtitle Translation Studio
SRT Engine: Robust parser, timecode math, and subtitle serializer.
"""

import os
import re
from typing import List, Dict, Tuple, Optional

def timecode_to_ms(tc: str) -> int:
    """Convert SRT timecode (00:01:23,456 or 00:01:23.456) to total milliseconds."""
    tc = tc.strip().replace('.', ',')
    parts = tc.split(':')
    if len(parts) != 3:
        return 0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_parts = parts[2].split(',')
        seconds = int(sec_parts[0])
        millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
        return ((hours * 3600 + minutes * 60 + seconds) * 1000) + millis
    except Exception:
        return 0

def ms_to_timecode(ms: int) -> str:
    """Convert total milliseconds to standard SRT timecode (HH:MM:SS,mmm)."""
    if ms < 0:
        ms = 0
    total_sec, millis = divmod(ms, 1000)
    hours, remainder = divmod(total_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

def strip_tags(text: str) -> str:
    """Remove HTML-like formatting tags for accurate character counting."""
    return re.sub(r'<[^>]+>', '', text).strip()

def calculate_cps(text: str, duration_sec: float) -> float:
    """Calculate Characters Per Second (CPS) based on clean text length and duration."""
    clean = strip_tags(text)
    if duration_sec <= 0 or not clean:
        return 0.0
    return round(len(clean) / duration_sec, 1)


class SrtEntry:
    def __init__(self, idx: int, start_time: str, end_time: str, source: str, trans: str = "", ai_ref: str = ""):
        self.idx = idx
        self.start_time = start_time.strip()
        self.end_time = end_time.strip()
        self.start_ms = timecode_to_ms(self.start_time)
        self.end_ms = timecode_to_ms(self.end_time)
        self.duration_sec = max(0.1, (self.end_ms - self.start_ms) / 1000.0)
        self.source = source.strip()
        self.trans = trans.strip()
        self.ai_ref = ai_ref.strip()
        self.is_verified = False

    @property
    def timecode_range(self) -> str:
        return f"{self.start_time} --> {self.end_time}"

    @property
    def cps(self) -> float:
        text_to_measure = self.trans if self.trans else self.source
        return calculate_cps(text_to_measure, self.duration_sec)

    @property
    def is_cps_warning(self) -> bool:
        # Standard subtitle rule: CPS > 25 is considered too fast for human reading
        return self.cps > 25.0

    def to_dict(self) -> Dict:
        return {
            "id": f"sub_{self.idx}",
            "index": self.idx,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_sec": self.duration_sec,
            "source": self.source,
            "trans": self.trans,
            "ai_ref": self.ai_ref,
            "cps": self.cps,
            "is_verified": self.is_verified
        }


class SrtEngine:
    """Engine for loading, parsing, and writing SubRip (.srt) files."""

    @staticmethod
    def load_srt(filepath: str) -> Tuple[List[SrtEntry], str]:
        """
        Loads an SRT file and returns a list of SrtEntry objects along with detected encoding.
        Supports UTF-8, UTF-8-SIG, TIS-620 (Thai ANSI), CP1252, Latin-1.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        encodings = ['utf-8-sig', 'utf-8', 'tis-620', 'cp874', 'cp1252', 'latin-1']
        content = ""
        used_encoding = 'utf-8-sig'

        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                used_encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not content:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            used_encoding = 'utf-8'

        entries = SrtEngine.parse_srt_content(content)
        return entries, used_encoding

    @staticmethod
    def parse_srt_content(content: str) -> List[SrtEntry]:
        """Parses raw SRT text content into a list of SrtEntry objects."""
        content = content.replace('\r\n', '\n').replace('\r', '\n').strip()
        blocks = re.split(r'\n\s*\n', content)

        entries = []
        parsed_idx = 1

        for block in blocks:
            lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
            if not lines:
                continue

            time_line_idx = -1
            for i, line in enumerate(lines):
                if '-->' in line:
                    time_line_idx = i
                    break

            if time_line_idx == -1:
                continue

            if time_line_idx > 0:
                try:
                    idx = int(re.sub(r'\D', '', lines[0]))
                except ValueError:
                    idx = parsed_idx
            else:
                idx = parsed_idx

            time_line = lines[time_line_idx]
            time_parts = time_line.split('-->')
            if len(time_parts) != 2:
                continue
            start_tc = time_parts[0].strip()
            end_tc = time_parts[1].strip()

            text_lines = lines[time_line_idx + 1:]
            text = '\n'.join(text_lines).strip()

            entry = SrtEntry(
                idx=idx,
                start_time=start_tc,
                end_time=end_tc,
                source=text,
                trans="",
                ai_ref=""
            )
            entries.append(entry)
            parsed_idx += 1

        return entries

    @staticmethod
    def save_srt(filepath: str, entries: List[SrtEntry], mode: str = "trans_fallback_source", encoding: str = "utf-8-sig") -> None:
        """
        Saves entries to an SRT file.
        Modes:
        - 'trans_fallback_source': Use translation if available, otherwise original source.
        - 'trans_only': Only use translation (empty string if untranslated).
        - 'dual_thai_top': Line 1: Thai translation, Line 2: Original English.
        - 'dual_eng_top': Line 1: Original English, Line 2: Thai translation.
        - 'source_only': Output original source.
        """
        with open(filepath, 'w', encoding=encoding, newline='\n') as f:
            for i, entry in enumerate(entries, start=1):
                f.write(f"{i}\n")
                f.write(f"{entry.start_time} --> {entry.end_time}\n")

                if mode == "trans_fallback_source":
                    out_text = entry.trans if entry.trans.strip() else entry.source
                elif mode == "trans_only":
                    out_text = entry.trans.strip()
                elif mode == "dual_thai_top":
                    th = entry.trans.strip() if entry.trans.strip() else entry.source
                    en = entry.source.strip()
                    out_text = f"{th}\n{en}" if th != en else th
                elif mode == "dual_eng_top":
                    th = entry.trans.strip() if entry.trans.strip() else entry.source
                    en = entry.source.strip()
                    out_text = f"{en}\n{th}" if th != en else en
                elif mode == "source_only":
                    out_text = entry.source
                else:
                    out_text = entry.trans if entry.trans.strip() else entry.source

                f.write(f"{out_text}\n\n")