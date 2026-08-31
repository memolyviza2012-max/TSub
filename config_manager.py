# -*- coding: utf-8 -*-
"""
TSub Standalone - Configuration, Profile, Glossary & Prompt Manager
Self-contained profile persistence with zero external dependencies.
"""

import os
import sys
import json
from typing import Dict, Any, List
from tsub_prompts import DEFAULT_SUBTITLE_PROMPT, DEFAULT_SUBTITLE_OPTIONS_PROMPT, CINEMATIC_MODES

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "tsub_config.json")
PROFILES_PATH = os.path.join(BASE_DIR, "tsub_profiles.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "OpenAI",
    "model": "gpt-4o-mini",
    "openai_key": "",
    "deepseek_key": "",
    "google_key": "",
    "anthropic_key": "",
    "base_url": "",
    "temperature": 0.3,
    "max_tokens": 4096,
    "timeout": 60,
    "last_dir": ""
}

DEFAULT_PROFILE_TEMPLATE: Dict[str, Any] = {
    "media_title": "",
    "media_type": "🎬 ภาพยนตร์ (Live-Action Movie)",
    "source_language": "English",
    "target_language": "Thai",
    "main_prompt": DEFAULT_SUBTITLE_PROMPT,
    "options_prompt": DEFAULT_SUBTITLE_OPTIONS_PROMPT,
    "project_lore": "",
    "cinematic_modes": CINEMATIC_MODES.copy(),
    "glossary": {}
}

FALLBACK_SOURCES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tsub_config.json"),
    r"E:\Mod_Workspace\Modder_project\modder-hub\tools\Standalone\TSub\tsub_config.json",
    os.path.join(os.path.expanduser("~"), ".tsub", "tsub_config.json")
]

FALLBACK_PROFILES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tsub_profiles.json"),
    r"E:\Mod_Workspace\Modder_project\modder-hub\tools\Standalone\TSub\tsub_profiles.json",
    os.path.join(os.path.expanduser("~"), ".tsub", "tsub_profiles.json")
]

class ConfigManager:
    @staticmethod
    def load_config() -> Dict[str, Any]:
        cfg = DEFAULT_CONFIG.copy()
        target_file = CONFIG_PATH
        if not os.path.exists(target_file):
            for fb in FALLBACK_SOURCES:
                if os.path.exists(fb):
                    target_file = fb
                    break

        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    cfg.update(saved)
            except Exception as e:
                print(f"[TSub Config] Error reading config: {e}")
        return cfg

    @staticmethod
    def save_config(data: Dict[str, Any]) -> None:
        for path in [CONFIG_PATH, r"E:\Mod_Workspace\Modder_project\modder-hub\tools\Standalone\TSub\tsub_config.json"]:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                pass

    # ── Profiles Management ───────────────────────────────────────────────────
    @staticmethod
    def load_profiles() -> Dict[str, Any]:
        target_file = PROFILES_PATH
        if not os.path.exists(target_file):
            for fb in FALLBACK_PROFILES:
                if os.path.exists(fb):
                    target_file = fb
                    break

        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[TSub Profiles] Error reading profiles: {e}")

        # Default fallback
        return {
            "active_profile": "Default",
            "presets": {
                "Default": DEFAULT_PROFILE_TEMPLATE.copy()
            }
        }

    @staticmethod
    def save_profiles(data: Dict[str, Any]) -> None:
        for path in [PROFILES_PATH, r"E:\Mod_Workspace\Modder_project\modder-hub\tools\Standalone\TSub\tsub_profiles.json"]:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                pass

    @staticmethod
    def get_profile_list() -> List[str]:
        data = ConfigManager.load_profiles()
        return list(data.get("presets", {}).keys())

    @staticmethod
    def get_active_profile_name() -> str:
        data = ConfigManager.load_profiles()
        return data.get("active_profile", "Default")

    @staticmethod
    def set_active_profile_name(name: str) -> None:
        data = ConfigManager.load_profiles()
        if name in data.get("presets", {}):
            data["active_profile"] = name
            ConfigManager.save_profiles(data)

    @staticmethod
    def get_active_profile_data() -> Dict[str, Any]:
        data = ConfigManager.load_profiles()
        active = data.get("active_profile", "Default")
        presets = data.get("presets", {})
        if active not in presets:
            presets[active] = DEFAULT_PROFILE_TEMPLATE.copy()
            data["presets"] = presets
            ConfigManager.save_profiles(data)
        
        prof = DEFAULT_PROFILE_TEMPLATE.copy()
        prof.update(presets[active])
        return prof

    @staticmethod
    def save_active_profile_data(prof_data: Dict[str, Any]) -> None:
        data = ConfigManager.load_profiles()
        active = data.get("active_profile", "Default")
        if "presets" not in data:
            data["presets"] = {}
        data["presets"][active] = prof_data
        ConfigManager.save_profiles(data)

    @staticmethod
    def create_profile(name: str, copy_from: str = "") -> None:
        data = ConfigManager.load_profiles()
        presets = data.setdefault("presets", {})
        if copy_from and copy_from in presets:
            new_data = json.loads(json.dumps(presets[copy_from]))
        else:
            new_data = DEFAULT_PROFILE_TEMPLATE.copy()
        presets[name] = new_data
        data["active_profile"] = name
        ConfigManager.save_profiles(data)

    @staticmethod
    def delete_profile(name: str) -> None:
        data = ConfigManager.load_profiles()
        presets = data.get("presets", {})
        if name in presets and len(presets) > 1:
            del presets[name]
            if data.get("active_profile") == name:
                data["active_profile"] = list(presets.keys())[0]
            ConfigManager.save_profiles(data)

    @staticmethod
    def rename_profile(old_name: str, new_name: str) -> None:
        data = ConfigManager.load_profiles()
        presets = data.get("presets", {})
        if old_name in presets and new_name and new_name not in presets:
            presets[new_name] = presets.pop(old_name)
            if data.get("active_profile") == old_name:
                data["active_profile"] = new_name
            ConfigManager.save_profiles(data)

    # ── Proxy Getters/Setters for Active Profile ──────────────────────────────
    @staticmethod
    def load_glossary() -> Dict[str, str]:
        prof = ConfigManager.get_active_profile_data()
        return prof.get("glossary", {})

    @staticmethod
    def save_glossary(glossary_data: Dict[str, str]) -> None:
        prof = ConfigManager.get_active_profile_data()
        prof["glossary"] = glossary_data
        ConfigManager.save_active_profile_data(prof)

    @staticmethod
    def load_prompts() -> Dict[str, Any]:
        return ConfigManager.get_active_profile_data()

    @staticmethod
    def save_prompts(prompts_data: Dict[str, Any]) -> None:
        prof = ConfigManager.get_active_profile_data()
        prof.update(prompts_data)
        ConfigManager.save_active_profile_data(prof)