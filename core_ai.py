# -*- coding: utf-8 -*-
"""
TSub Standalone - AI Engine & Multi-API Client
Zero-dependency AI translation client with session pooling and async worker support.
"""

import json
import re
import requests
from requests.adapters import HTTPAdapter
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

# Shared HTTP session for fast keep-alive connections
_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
_session.mount('http://', _adapter)
_session.mount('https://', _adapter)

class WorkerSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class ApiWorker(QRunnable):
    _active_signals = set()

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        ApiWorker._active_signals.add(self.signals)
        self.signals.finished.connect(self._cleanup)
        self.signals.error.connect(self._cleanup)

    def _cleanup(self, *args):
        try:
            ApiWorker._active_signals.remove(self.signals)
        except KeyError:
            pass

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

class ThreadSafeWorkerSignalsForwarder(QObject):
    signal_finished = pyqtSignal(str)
    signal_error = pyqtSignal(str)

    def __init__(self, on_success, on_error, parent=None):
        super().__init__(parent)
        self.on_success = on_success
        self.on_error = on_error
        self.signal_finished.connect(self.on_success)
        self.signal_error.connect(self.on_error)

    def handle_finished(self, result):
        self.signal_finished.emit(result)

    def handle_error(self, err):
        self.signal_error.emit(err)


class CoreAI:
    @staticmethod
    def generate_content(cfg: dict, prompt: str, is_local: bool = False) -> str:
        model = cfg.get("model", "gpt-4o-mini")
        provider = cfg.get("provider", "OpenAI")
        if is_local or provider == "Local LLM":
            model = "custom-local-llm"

        # Validate keys
        if model != "custom-local-llm" and provider != "Local LLM":
            if provider == "Google Gemini" and not cfg.get("google_key"):
                raise Exception("Google Gemini API Key is missing! Please configure it in Settings.")
            elif provider == "Anthropic Claude" and not cfg.get("anthropic_key"):
                raise Exception("Anthropic Claude API Key is missing! Please configure it in Settings.")
            elif provider == "DeepSeek" and not cfg.get("deepseek_key"):
                raise Exception("DeepSeek API Key is missing! Please configure it in Settings.")
            elif provider == "OpenAI" and not cfg.get("openai_key"):
                raise Exception("OpenAI API Key is missing! Please configure it in Settings.")

        timeout_val = cfg.get("timeout", 60)
        temp_val = float(cfg.get("temperature", 0.3))
        max_tokens_val = int(cfg.get("max_tokens", 4096))
        base_url = cfg.get("base_url", "").rstrip("/")

        content = ""

        # 1. Google Gemini
        if provider == "Google Gemini" or model.startswith("gemini"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg['google_key']}"
            if base_url:
                if "generateContent" not in base_url:
                    url = f"{base_url}/v1beta/models/{model}:generateContent?key={cfg['google_key']}"
                else:
                    url = f"{base_url}?key={cfg['google_key']}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temp_val, "maxOutputTokens": max_tokens_val}
            }
            res = _session.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=timeout_val)
            if res.status_code == 200:
                try:
                    content = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception as e:
                    raise Exception(f"Gemini response parsing error: {e}, data: {res.text}")
            else:
                raise Exception(f"Gemini API Error {res.status_code}: {res.text}")

        # 2. Anthropic Claude
        elif provider == "Anthropic Claude" or model.startswith("claude"):
            url = "https://api.anthropic.com/v1/messages"
            if base_url:
                url = f"{base_url}/v1/messages" if not base_url.endswith("/messages") else base_url
            headers = {
                "x-api-key": cfg["anthropic_key"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens_val,
                "temperature": temp_val,
                "messages": [{"role": "user", "content": prompt}]
            }
            res = _session.post(url, json=payload, headers=headers, timeout=timeout_val)
            if res.status_code == 200:
                content = res.json()["content"][0]["text"].strip()
            else:
                raise Exception(f"Claude API Error {res.status_code}: {res.text}")

        # 3. DeepSeek
        elif provider == "DeepSeek" or model.startswith("deepseek"):
            url = "https://api.deepseek.com/chat/completions"
            if base_url:
                url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
            headers = {"Authorization": f"Bearer {cfg['deepseek_key']}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "temperature": temp_val,
                "max_tokens": max_tokens_val,
                "messages": [{"role": "user", "content": prompt}]
            }
            res = _session.post(url, json=payload, headers=headers, timeout=timeout_val)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"DeepSeek API Error {res.status_code}: {res.text}")

        # 4. Local LLM (LM Studio / Ollama)
        elif provider == "Local LLM" or model == "custom-local-llm":
            url = base_url if base_url else "http://localhost:1234/v1/chat/completions"
            if not url.endswith("/chat/completions"):
                url = f"{url.rstrip('/')}/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": "local-model",
                "temperature": temp_val,
                "max_tokens": max_tokens_val,
                "messages": [{"role": "user", "content": prompt}]
            }
            try:
                res = _session.post(url, json=payload, headers=headers, timeout=timeout_val)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"].strip()
                else:
                    raise Exception(f"Local API Error {res.status_code}: {res.text}")
            except requests.exceptions.ConnectionError:
                raise Exception(f"Could not connect to Local LLM at {url}. Make sure your LM Studio or Ollama server is running.")

        # 5. OpenAI Standard
        else:
            url = "https://api.openai.com/v1/chat/completions"
            if base_url:
                url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
            headers = {"Authorization": f"Bearer {cfg['openai_key']}", "Content-Type": "application/json"}
            
            if model.startswith(("o1", "o3", "o4")):
                payload = {
                    "model": model,
                    "max_completion_tokens": max_tokens_val,
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                payload = {
                    "model": model,
                    "temperature": temp_val,
                    "max_tokens": max_tokens_val,
                    "messages": [{"role": "user", "content": prompt}]
                }

            res = _session.post(url, json=payload, headers=headers, timeout=timeout_val)
            if res.status_code == 200:
                try:
                    content = res.json()["choices"][0]["message"]["content"].strip()
                except Exception as e:
                    raise Exception(f"OpenAI parsing error: {e}, response: {res.text}")
            else:
                try:
                    err_msg = res.json().get("error", {}).get("message", res.text)
                except Exception:
                    err_msg = res.text
                raise Exception(f"OpenAI API Error {res.status_code}: {err_msg}")

        # Post-process: Convert Thai numerals to Arabic numerals
        thai_to_arabic = str.maketrans('๑๒๓๔๕๖๗๘๙๐', '1234567890')
        return content.translate(thai_to_arabic)