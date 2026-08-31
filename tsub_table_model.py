# -*- coding: utf-8 -*-
"""
TSub - Subtitle Translation Studio
Virtualized Table Model & Filter Proxy for Subtitle Grids.
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QBrush, QFont
from srt_engine import SrtEntry

COL_IDX = 0
COL_TIMECODE = 1
COL_DURATION = 2
COL_CPS = 3
COL_SOURCE = 4
COL_TRANS = 5
COL_AI_REF = 6

COL_HEADERS = [
    "#",
    "⏱️ Timecode",
    "⏳ Duration",
    "⚡ CPS",
    "Original Subtitle (Source)",
    "Thai Translation",
    "AI Reference"
]

class SubtitleTableModel(QAbstractTableModel):
    def __init__(self, entries: Optional[List[SrtEntry]] = None, parent=None):
        super().__init__(parent)
        self.entries: List[SrtEntry] = entries or []
        self.is_dirty = False

    def rowCount(self, parent=QModelIndex()):
        return len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return len(COL_HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(COL_HEADERS):
                return COL_HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.entries)):
            return None

        entry = self.entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == COL_IDX:
                return str(entry.idx)
            elif col == COL_TIMECODE:
                return entry.timecode_range
            elif col == COL_DURATION:
                return f"{entry.duration_sec:.1f}s"
            elif col == COL_CPS:
                return f"{entry.cps:.1f}"
            elif col == COL_SOURCE:
                return entry.source.replace('\n', ' ↵ ')
            elif col == COL_TRANS:
                return entry.trans.replace('\n', ' ↵ ')
            elif col == COL_AI_REF:
                return entry.ai_ref.replace('\n', ' ↵ ')

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [COL_IDX, COL_TIMECODE, COL_DURATION, COL_CPS]:
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_CPS:
                if entry.cps > 25.0:
                    return QBrush(QColor("#f38ba8"))  # Red warning
                elif entry.cps > 20.0:
                    return QBrush(QColor("#fab387"))  # Orange caution
                return QBrush(QColor("#a6e3a1"))      # Green good
            elif col == COL_TRANS and entry.trans:
                return QBrush(QColor("#a6e3a1"))      # Green translated
            elif col == COL_SOURCE:
                return QBrush(QColor("#cdd6f4"))

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == COL_CPS and entry.cps > 25.0:
                return QBrush(QColor(243, 139, 168, 30))
            if index.row() % 2 == 1:
                return QBrush(QColor("#181825"))     # Subtle zebra striping
            return QBrush(QColor("#1e1e2e"))

        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() in [COL_TRANS, COL_AI_REF]:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()
        entry = self.entries[row]
        str_val = str(value)

        if col == COL_TRANS:
            entry.trans = str_val
            self.is_dirty = True
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            # Update CPS column as well
            cps_idx = self.index(row, COL_CPS)
            self.dataChanged.emit(cps_idx, cps_idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            return True
        elif col == COL_AI_REF:
            entry.ai_ref = str_val
            self.is_dirty = True
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True

        return False

    def update_trans(self, row: int, new_text: str):
        if 0 <= row < len(self.entries):
            self.entries[row].trans = new_text
            self.is_dirty = True
            idx_trans = self.index(row, COL_TRANS)
            idx_cps = self.index(row, COL_CPS)
            self.dataChanged.emit(idx_trans, idx_trans, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            self.dataChanged.emit(idx_cps, idx_cps, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])

    def update_ai_ref(self, row: int, new_text: str):
        if 0 <= row < len(self.entries):
            self.entries[row].ai_ref = new_text
            self.is_dirty = True
            idx = self.index(row, COL_AI_REF)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def set_entries(self, entries: List[SrtEntry]):
        self.beginResetModel()
        self.entries = entries
        self.is_dirty = False
        self.endResetModel()


class SubtitleFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_mode = "all"  # "all", "untranslated", "translated", "high_cps"
        self.search_keyword = ""

    def set_filter_mode(self, mode: str):
        self.filter_mode = mode
        self.invalidateFilter()

    def set_search_keyword(self, keyword: str):
        self.search_keyword = keyword.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model: SubtitleTableModel = self.sourceModel()
        if not model or not (0 <= source_row < len(model.entries)):
            return False

        entry = model.entries[source_row]

        # Mode filter
        if self.filter_mode == "untranslated" and entry.trans.strip():
            return False
        elif self.filter_mode == "translated" and not entry.trans.strip():
            return False
        elif self.filter_mode == "high_cps" and not entry.is_cps_warning:
            return False

        # Keyword filter
        if self.search_keyword:
            kw = self.search_keyword
            if kw not in entry.source.lower() and kw not in entry.trans.lower() and kw not in entry.ai_ref.lower() and kw not in str(entry.idx):
                return False

        return True