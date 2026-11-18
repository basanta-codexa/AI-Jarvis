"""
J.A.R.V.I.S. — simple voice-first interface.

One screen, nothing else:
  top bar    — real status (AI online/offline, mic availability)
  centre     — clickable arc reactor (click to talk) with a state caption
  below      — slim chat area (only visible once there are messages)
  chips row  — quick commands
  bottom     — one input row with a big mic button

Plain customtkinter + tkinter.Canvas. No external UI dependencies.
"""
from __future__ import annotations

import math
import threading
import tkinter as tk

import customtkinter as ctk

from ai_jarvis.config.settings import (
    COLOR_BG_DEEP, COLOR_BG_SURFACE, COLOR_BG_GLASS, COLOR_ACCENT,
    COLOR_ACCENT_DIM, COLOR_ACCENT_RED, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_TEXT_DIM, COLOR_SUCCESS, COLOR_WARNING,
    WINDOW_TITLE, FONT_UI, FONT_MONO_SMALL, USER_NAME, JARVIS_NAME,
)

# Window geometry (kept local on purpose — this is a personal app, not a theme)
WINDOW_W, WINDOW_H = 1000, 720
ORB_SIZE = 240          # reactor canvas edge, px
PULSE_MS = 50           # ~20 fps — calmer, smoother motion


def status_line(status: dict) -> str:
    """One honest status line from orchestrator.get_status(). No invented numbers."""
    ai = status.get("ai", "offline")
    base = {
        "online": "Online",
        "configured": "Key set (unverified)",
    }.get(ai, "Offline mode")
    mic = "mic ready" if status.get("stt") == "online" else "no mic"
    memory = "memory on" if status.get("memory", {}).get("vector_memory") == "online" else "memory basic"
    return f"{base} · {mic} · {memory}"


def _lerp(a: str, b: str, t: float) -> str:
    """Blend two '#rrggbb' colours (t=0 → a, t=1 → b)."""
    ca, cb = (int(a[i:i + 2], 16) for i in (1, 3, 5)), (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


class JarvisGUI:
    """Single-screen, voice-first interface."""

    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.orch.on_message = self._on_message

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        self.root.configure(fg_color=COLOR_BG_DEEP)
        self._center(WINDOW_W, WINDOW_H)
        self.root.minsize(760, 560)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._listening = False
        self._pulse = 0.0
        self._placeholder = None

        self._build_top_bar()
        self._build_orb()
        self._build_chat()
        self._build_quick_commands()
        self._build_input_bar()

        # Wire voice feedback: level meter + re-listen when JARVIS finishes speaking
        if hasattr(self.orch.stt, "on_volume"):
            self.orch.stt.on_volume = lambda v: self.root.after(0, self._set_level, v)
        if hasattr(self.orch.tts, "on_idle"):
            self.orch.tts.on_idle = lambda: self.root.after(0, self._auto_listen)

        self._refresh_status()
        self._animate()
        self.root.after(800, self._greet)

    # ─────────────────────────────────────────────────────────────
    #  Layout
    # ─────────────────────────────────────────────────────────────

    def _center(self, w: int, h: int):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(w, sw - 80), min(h, sh - 80)
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build_top_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent", height=36)
        bar.pack(fill="x", padx=18, pady=(12, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar, text=JARVIS_NAME, font=FONT_MONO_SMALL, text_color=COLOR_ACCENT,
        ).pack(side="left")

        self.status_dot = ctk.CTkLabel(
            bar, text="●", font=FONT_MONO_SMALL, text_color=COLOR_WARNING,
        )
        self.status_dot.pack(side="left", padx=(10, 4))
        self.status_var = tk.StringVar(value="Starting…")
        ctk.CTkLabel(
            bar, textvariable=self.status_var, font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

    def _build_orb(self):
        self.orb = tk.Canvas(
            self.root, width=ORB_SIZE, height=ORB_SIZE,
            bg=COLOR_BG_DEEP, highlightthickness=0,
        )
        self.orb.pack(pady=(10, 2))
        self.orb.bind("<Button-1>", lambda _e: self._toggle_mic())
        self.orb.configure(cursor="hand2")

        self.caption_var = tk.StringVar(value="Ready. How can I help?")
        ctk.CTkLabel(
            self.root, textvariable=self.caption_var,
            font=FONT_UI, text_color=COLOR_TEXT_SECONDARY,
        ).pack()

        # Voice-level meter — fills with your voice, empty when idle
        self.level = tk.Canvas(
            self.root, width=320, height=6, bg=COLOR_BG_DEEP, highlightthickness=0
        )
        self.level.pack(pady=(6, 0))
        self._level_bar = self.level.create_rectangle(0, 0, 0, 6, fill=COLOR_ACCENT, width=0)

    def _set_level(self, level: float):
        width = int(320 * max(0.0, min(1.0, level)))
        self.level.coords(self._level_bar, 0, 0, width, 6)

    def _build_chat(self):
        self.chat = ctk.CTkScrollableFrame(
            self.root, fg_color="transparent",
        )
        self.chat.pack(fill="both", expand=True, padx=90, pady=8)
        self.chat.grid_columnconfigure(0, weight=1)

        self._placeholder = ctk.CTkLabel(
            self.chat, text="Your conversation will appear here.",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
        )
        self._placeholder.pack(pady=20)

    def _build_quick_commands(self):
        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.pack(fill="x", padx=90, pady=(0, 4))

        for label, cmd in [
            ("TIME", "what time is it"),
            ("DATE", "what is today's date"),
            ("STATUS", "system status"),
            ("MEMORY", "what do you remember"),
            ("JOKE", "tell me a joke"),
        ]:
            ctk.CTkButton(
                row, text=label, command=lambda c=cmd: self._send(c),
                font=FONT_MONO_SMALL, height=30, corner_radius=15,
                fg_color=COLOR_BG_GLASS, border_color=COLOR_ACCENT_DIM,
                border_width=1, text_color=COLOR_TEXT_SECONDARY,
                hover_color=COLOR_BG_SURFACE,
            ).pack(side="left", padx=(0, 8))

    def _build_input_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.pack(fill="x", padx=90, pady=(0, 18))

        self.entry = ctk.CTkEntry(
            bar, placeholder_text="Ask JARVIS anything…",
            font=FONT_UI, height=44, corner_radius=22,
            fg_color=COLOR_BG_GLASS, border_color=COLOR_ACCENT_DIM,
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _e: self._send_from_entry())
        self.entry.focus_set()

        ctk.CTkButton(
            bar, text="Send", width=70, height=44, corner_radius=22,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_DIM,
            text_color=COLOR_BG_DEEP, font=ctk.CTkFont(weight="bold"),
            command=self._send_from_entry,
        ).pack(side="left", padx=(8, 0))

        self.mic_btn = ctk.CTkButton(
            bar, text="MIC", width=64, height=44, corner_radius=22,
            font=FONT_MONO_SMALL,
            fg_color=COLOR_ACCENT_DIM, hover_color=COLOR_BG_GLASS,
            command=self._toggle_mic,
        )
        self.mic_btn.pack(side="left", padx=(8, 0))

    # ─────────────────────────────────────────────────────────────
    #  Orb — a clean, minimal concentric ring that breathes gently
    # ─────────────────────────────────────────────────────────────

    def _draw_orb(self):
        c, cx = self.orb, ORB_SIZE / 2
        c.delete("orb")
        wave = 0.5 + 0.5 * math.sin(self._pulse)
        accent = COLOR_ACCENT_RED if self._listening else COLOR_ACCENT

        # Faint guide ring
        c.create_oval(8, 8, ORB_SIZE - 8, ORB_SIZE - 8,
                      outline=COLOR_ACCENT_DIM, width=1, tags="orb")

        # Two soft rings that breathe — blended toward the background
        for radius, strength in ((0.40, 0.20), (0.30, 0.32)):
            r = ORB_SIZE * radius * (0.97 + 0.03 * wave)
            c.create_oval(cx - r, cx - r, cx + r, cx + r,
                          outline=_lerp(COLOR_BG_DEEP, accent, strength),
                          width=2, tags="orb")

        # Solid core with a crisp accent outline
        core = ORB_SIZE * 0.115 * (0.97 + 0.05 * wave)
        c.create_oval(cx - core, cx - core, cx + core, cx + core,
                      fill=_lerp(COLOR_BG_SURFACE, accent, 0.25),
                      outline=accent, width=2, tags="orb")

        # Bright centre dot
        dot = core * 0.22
        c.create_oval(cx - dot, cx - dot, cx + dot, cx + dot,
                      fill=accent, outline="", tags="orb")

    def _animate(self):
        # Exit skill requested a real shutdown — stop drawing, say goodbye, close
        if getattr(self.orch, "request_shutdown", False):
            self._begin_graceful_close()
            return
        self._pulse += 0.08
        self._draw_orb()
        self.root.after(PULSE_MS, self._animate)

    # ─────────────────────────────────────────────────────────────
    #  Status (real values only)
    # ─────────────────────────────────────────────────────────────

    def _refresh_status(self):
        try:
            status = self.orch.get_status()
        except Exception:
            self.status_var.set("Offline mode")
            self.status_dot.configure(text_color=COLOR_WARNING)
            return
        self.status_var.set(status_line(status))
        self.status_dot.configure(
            text_color=COLOR_SUCCESS if status.get("ai") == "online" else COLOR_WARNING,
        )

    # ─────────────────────────────────────────────────────────────
    #  Conversation
    # ─────────────────────────────────────────────────────────────

    def _on_message(self, role: str, text: str):
        """Orchestrator callback (called from a worker thread)."""
        if getattr(self, "_closing", False):
            return
        self.root.after(0, self._add_bubble, role, text)

    def _add_bubble(self, role: str, text: str):
        if self._placeholder is not None:
            self._placeholder.destroy()
            self._placeholder = None

        is_user = role == "user"
        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.pack(fill="x", pady=3)
        bubble = ctk.CTkLabel(
            row, text=text, font=FONT_UI, justify="left",
            wraplength=520, corner_radius=12, padx=12, pady=8,
            fg_color=COLOR_BG_GLASS if is_user else COLOR_BG_SURFACE,
            text_color=COLOR_TEXT_PRIMARY,
        )
        bubble.pack(anchor="e" if is_user else "w")

        # customtkinter exposes no public scroll API — nudge to bottom.
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

        if role != "user":
            self._refresh_status()
            self.caption_var.set("Ready. How can I help?")

    def _send_from_entry(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._send(text)

    def _send(self, text: str):
        self.caption_var.set("Thinking…")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text: str):
        try:
            self.orch.process_sync(text)
        except Exception as exc:
            self.root.after(0, self._add_bubble, "error", f"Something went wrong: {exc}")
            self.root.after(0, self.caption_var.set, "Ready. How can I help?")

    # ─────────────────────────────────────────────────────────────
    #  Voice
    # ─────────────────────────────────────────────────────────────

    def _toggle_mic(self):
        if self._listening:
            self._stop_listening("Stopped. How can I help?")
            return
        self._start_listening()

    def _start_listening(self):
        if not getattr(self.orch.stt, "is_available", False):
            reason = getattr(self.orch.stt, "unavailable_reason", "")
            self.caption_var.set(f"Microphone unavailable — {reason or 'check microphone'}")
            return
        self._listening = True
        if hasattr(self.orch.stt, "on_speech_start"):
            self.orch.stt.on_speech_start = lambda: self.root.after(
                0, self.caption_var.set, "Hearing you — keep talking…"
            )
        self.mic_btn.configure(text="STOP", fg_color=COLOR_ACCENT_RED)
        self.caption_var.set("Listening… say something")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _auto_listen(self):
        """Hands-free: after JARVIS finishes speaking, listen for a follow-up."""
        if not self._listening:
            self._start_listening()

    def _stop_listening(self, caption: str):
        self._listening = False
        if hasattr(self.orch.stt, "on_speech_start"):
            self.orch.stt.on_speech_start = None
        self.mic_btn.configure(text="MIC", fg_color=COLOR_ACCENT_DIM)
        self.caption_var.set(caption)
        self._set_level(0.0)

    def _listen_loop(self):
        while self._listening:
            try:
                text = self.orch.stt.listen()
            except Exception as e:
                text = None
                self.orch.stt.last_error = f"Microphone error ({e})"
            if text and self._listening:
                self._listening = False
                if hasattr(self.orch.stt, "on_speech_start"):
                    self.orch.stt.on_speech_start = None
                self.root.after(0, lambda: self.mic_btn.configure(text="MIC", fg_color=COLOR_ACCENT_DIM))
                self.root.after(0, self.caption_var.set, "Thinking…")
                self.root.after(0, self._send, text)
                return
            error = getattr(self.orch.stt, "last_error", None)
            if error:
                # Stop cleanly instead of silently listening forever
                self._listening = False
                if hasattr(self.orch.stt, "on_speech_start"):
                    self.orch.stt.on_speech_start = None
                self.root.after(
                    0, lambda: self.mic_btn.configure(text="MIC", fg_color=COLOR_ACCENT_DIM)
                )
                self.root.after(0, self.caption_var.set, error)
                self.root.after(0, self._set_level, 0.0)
                return
            # No speech within STT_TIMEOUT and no error — quietly go back to Ready
            self._listening = False
            if hasattr(self.orch.stt, "on_speech_start"):
                self.orch.stt.on_speech_start = None
            self.root.after(
                0, lambda: self.mic_btn.configure(text="MIC", fg_color=COLOR_ACCENT_DIM)
            )
            self.root.after(0, self.caption_var.set, "Ready. How can I help?")
            self.root.after(0, self._set_level, 0.0)
            return

    # ─────────────────────────────────────────────────────────────
    #  Lifecycle
    # ─────────────────────────────────────────────────────────────

    def _begin_graceful_close(self):
        """Wait for the goodbye to be spoken, then close the window."""
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self.caption_var.set("Shutting down…")
        try:
            self.entry.configure(state="disabled")
        except Exception:
            pass
        if getattr(self.orch.tts, "is_available", False) and hasattr(self.orch.tts, "on_idle"):
            # on_idle fires when the speech queue drains — perfect "goodbye done" signal
            self.orch.tts.on_idle = lambda: self.root.after(0, self._on_close)
            self.root.after(15_000, self._close_if_closing)   # safety net
        else:
            self._on_close()

    def _close_if_closing(self):
        if getattr(self, "_closing", False):
            self._on_close()

    def _greet(self):
        if getattr(self, "_closing", False):
            return
        greeting = f"Hello {USER_NAME}. {JARVIS_NAME} is online."
        self._add_bubble("jarvis", greeting)
        self.orch.tts.speak(greeting)

    def _on_close(self):
        self._listening = False
        try:
            self.orch.shutdown()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
