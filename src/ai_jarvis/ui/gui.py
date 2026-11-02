"""
J.A.R.V.I.S. Cinematic GUI
Iron Man-inspired interface with holographic HUD, arc reactor, audio visualizer,
scanning lines, particle effects, and glassmorphism panels.
"""
from __future__ import annotations

import math
import random
import threading
import time
import tkinter as tk

import customtkinter as ctk

from ai_jarvis.config.settings import (
    COLOR_BG_DEEP, COLOR_BG, COLOR_BG_SURFACE, COLOR_BG_GLASS,
    COLOR_ACCENT, COLOR_ACCENT_GLOW, COLOR_ACCENT_DIM, COLOR_ACCENT_PURPLE,
    COLOR_ACCENT_RED, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_DIM,
    COLOR_TEXT_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LISTENING,
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, FONT_HEADER, FONT_SUBHEADER,
    FONT_MONO, FONT_MONO_SMALL, FONT_UI, USER_NAME, JARVIS_NAME,
)


class Particle:
    """A floating dust particle for the holographic effect."""

    def __init__(self, canvas, w, h):
        self.canvas = canvas
        self.w = w
        self.h = h
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.size = random.uniform(0.5, 2.5)
        self.speed = random.uniform(0.2, 0.8)
        self.angle = random.uniform(0, 2 * math.pi)
        self.alpha = random.uniform(0.1, 0.6)
        self.id = canvas.create_oval(
            self.x, self.y, self.x + self.size, self.y + self.size,
            fill=COLOR_ACCENT, outline=""
        )

    def update(self):
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        if self.x < 0 or self.x > self.w or self.y < 0 or self.y > self.h:
            self.x = random.uniform(0, self.w)
            self.y = random.uniform(0, self.h)
        self.canvas.coords(
            self.id, self.x, self.y, self.x + self.size, self.y + self.size
        )


class JarvisGUI:
    """Cinematic J.A.R.V.I.S. interface."""

    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.orch.on_message = self._on_message

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(WINDOW_WIDTH, screen_width - 80)
        height = min(WINDOW_HEIGHT, screen_height - 100)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.configure(fg_color=COLOR_BG_DEEP)
        self.root.minsize(min(900, width), min(600, height))
        self.root.resizable(True, True)

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Animation state
        self._pulse_angle = 0
        self._scan_line_y = 0
        self._scan_direction = 1
        self._audio_level = 0
        self._is_listening = False
        self._typing_active = False
        self._typing_text = ""
        self._typing_index = 0
        self._typing_bubble = None
        self._particles = []
        self._frame_count = 0
        self._orbit_rings = []
        self._core_glow = []
        self._core_center = None

        self._build_ui()
        self._start_animations()

        # Greeting
        self.root.after(800, self._greet)

    # ═══════════════════════════════════════════════════════════════════
    #  UI BUILDING
    # ═══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Main container with deep space bg
        self.main = ctk.CTkFrame(self.root, fg_color=COLOR_BG_DEEP, corner_radius=0)
        self.main.pack(fill="both", expand=True)
        self.main.grid_columnconfigure(1, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # ── Left Sidebar (System Status + Comms) ──
        self._build_sidebar()

        # ── Center Main Area (Holographic Display) ──
        self._build_main_display()

        # ── Right Panel (Memory + AI Core) ──
        self._build_right_panel()

        # ── Bottom Input Bar ──
        self._build_input_bar()

        # ── Status Bar ──
        self._build_status_bar()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self.main, fg_color=COLOR_BG_SURFACE, width=240, corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_propagate(False)

        # Header
        header = ctk.CTkFrame(sidebar, fg_color="transparent", height=80)
        header.pack(fill="x", padx=20, pady=(25, 15))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="J.A.R.V.I.S.",
            font=FONT_HEADER, text_color=COLOR_ACCENT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header, text="NEURAL INTERFACE v2.0",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w")

        # System Status Panel
        self._add_panel(
            sidebar, "SYSTEM STATUS", COLOR_ACCENT, [
                ("AI Core", "ONLINE", COLOR_SUCCESS),
                ("Voice Engine", "ONLINE", COLOR_SUCCESS),
                ("Memory Vector", "ONLINE", COLOR_SUCCESS),
                ("Wake Word", "STANDBY", COLOR_WARNING),
            ],
        )

        # Comms Panel
        self._add_panel(
            sidebar, "COMMUNICATIONS", COLOR_ACCENT_PURPLE, [
                ("Uplink", "SECURE", COLOR_SUCCESS),
                ("Latency", "12ms", COLOR_SUCCESS),
                ("Bandwidth", "MAX", COLOR_SUCCESS),
            ],
        )

        # Quick Commands
        ctk.CTkLabel(
            sidebar, text="QUICK COMMANDS",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=20, pady=(25, 10))

        quick_cmds = [
            ("🕐 Time", "what time is it"),
            ("📅 Date", "what is today's date"),
            ("💻 System Status", "system status"),
            ("🧠 Memory", "what do you remember"),
            ("😄 Joke", "tell me a joke"),
            ("🌐 Open Google", "open google"),
        ]
        for label, cmd in quick_cmds:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                fg_color="transparent", hover_color=COLOR_ACCENT_DIM,
                border_color=COLOR_ACCENT, border_width=1,
                height=32, font=FONT_UI,
                command=lambda c=cmd: self._send_command(c),
            )
            btn.pack(fill="x", padx=20, pady=3)

    def _add_panel(self, parent, title, accent_color, items):
        panel = ctk.CTkFrame(parent, fg_color=COLOR_BG_GLASS, corner_radius=8)
        panel.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            panel, text=title, font=FONT_MONO_SMALL,
            text_color=accent_color,
        ).pack(anchor="w", padx=12, pady=(10, 5))

        for label, value, color in items:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(
                row, text=label, font=FONT_MONO_SMALL,
                text_color=COLOR_TEXT_SECONDARY,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value, font=FONT_MONO_SMALL,
                text_color=color,
            ).pack(side="right")

        # Store reference for updates
        setattr(self, f"panel_{title.lower().replace(' ', '_')}", panel)

    def _build_main_display(self):
        center = ctk.CTkFrame(self.main, fg_color=COLOR_BG_DEEP, corner_radius=0)
        center.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=3)
        center.grid_rowconfigure(1, weight=2)

        # Canvas for holographic effects
        self.canvas = tk.Canvas(
            center, bg=COLOR_BG_DEEP, highlightthickness=0,
            width=640, height=520,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=20, pady=(16, 8))
        self.canvas.bind("<Configure>", self._resize_display)

        # Keep the conversation separate from the animated display so neither
        # the reactor nor long replies get clipped by the other.
        self.chat_frame = ctk.CTkScrollableFrame(
            center, fg_color=COLOR_BG_DEEP,
        )
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self._msg_bubbles = []

    def _build_right_panel(self):
        right = ctk.CTkFrame(
            self.main, fg_color=COLOR_BG_SURFACE, width=280, corner_radius=0
        )
        right.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)
        right.grid_propagate(False)

        # Memory Panel
        self._add_panel(
            right, "MEMORY CORE", COLOR_ACCENT, [
                ("Vector DB", "ACTIVE", COLOR_SUCCESS),
                ("Short-term", "ACTIVE", COLOR_SUCCESS),
                ("Long-term", "ONLINE", COLOR_SUCCESS),
            ],
        )

        # AI Core Status
        ctk.CTkLabel(
            right, text="AI CORE", font=FONT_MONO_SMALL,
            text_color=COLOR_ACCENT_PURPLE,
        ).pack(anchor="w", padx=20, pady=(25, 5))

        self.ai_status = ctk.CTkLabel(
            right, text="STANDBY", font=FONT_SUBHEADER,
            text_color=COLOR_TEXT_DIM,
        )
        self.ai_status.pack(anchor="w", padx=20)

        # Activity log
        ctk.CTkLabel(
            right, text="ACTIVITY LOG", font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=20, pady=(20, 5))

        self.activity_log = ctk.CTkTextbox(
            right, width=260, height=200, fg_color=COLOR_BG_DEEP,
            text_color=COLOR_TEXT_PRIMARY, font=FONT_MONO_SMALL,
            border_color=COLOR_ACCENT_DIM, border_width=1,
        )
        self.activity_log.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _build_input_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SURFACE, height=90, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.grid_columnconfigure(1, weight=1, minsize=180)
        bar.grid_rowconfigure(0, weight=1)
        bar.grid_propagate(False)

        # Voice activity ring (canvas)
        self.voice_ring = tk.Canvas(
            bar, width=58, height=58, bg=COLOR_BG_SURFACE, highlightthickness=0
        )
        self.voice_ring.grid(row=0, column=0, padx=(14, 6), pady=10)
        self._ring_id = self.voice_ring.create_oval(
            7, 7, 51, 51, outline=COLOR_ACCENT_DIM, width=3
        )
        self._ring_fill = self.voice_ring.create_oval(
            17, 17, 41, 41, fill=COLOR_ACCENT, outline=""
        )

        # Text input
        self.input_entry = ctk.CTkEntry(
            bar,
            placeholder_text=f"Ask {JARVIS_NAME} anything…",
            font=FONT_UI, height=46, corner_radius=23,
            fg_color=COLOR_BG_DEEP, border_color=COLOR_ACCENT,
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=18)
        self.input_entry.bind("<Return>", lambda e: self._send_input())

        # Send button
        ctk.CTkButton(
            bar, text="SEND  ›", width=86, height=44,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_GLOW,
            text_color=COLOR_BG_DEEP, font=ctk.CTkFont(weight="bold"),
            corner_radius=23, command=self._send_input,
        ).grid(row=0, column=2, padx=(6, 8), pady=18)

        # Mic button
        self.mic_btn = ctk.CTkButton(
            bar, text="🎤", width=48, height=44,
            fg_color=COLOR_ACCENT_PURPLE, hover_color="#6d28d9",
            corner_radius=25, command=self._toggle_mic,
        )
        self.mic_btn.grid(row=0, column=3, padx=(4, 14), pady=18)

    def _build_status_bar(self):
        sb = ctk.CTkFrame(self.root, fg_color=COLOR_BG_DEEP, height=24, corner_radius=0)
        sb.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="Systems online. Awaiting command.")
        ctk.CTkLabel(
            sb, textvariable=self.status_var,
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(side="left", padx=20, pady=2)

        # Time
        self.time_var = tk.StringVar(value="00:00:00")
        ctk.CTkLabel(
            sb, textvariable=self.time_var,
            font=FONT_MONO, text_color=COLOR_ACCENT,
        ).pack(side="right", padx=20, pady=2)

    # ═══════════════════════════════════════════════════════════════════
    #  ANIMATIONS
    # ═══════════════════════════════════════════════════════════════════

    def _start_animations(self):
        # Create particles
        for _ in range(30):
            self._particles.append(
                Particle(self.canvas, self.canvas.winfo_width(), self.canvas.winfo_height())
            )
        self._resize_display()
        self._animate()

    def _resize_display(self, _event=None):
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        for particle in self._particles:
            particle.w = width
            particle.h = height
            if particle.x > width or particle.y > height:
                particle.x = random.uniform(0, width)
                particle.y = random.uniform(0, height)

        self.canvas.delete("reactor")
        self._orbit_rings.clear()
        self._core_glow.clear()
        center_x = width / 2
        center_y = height * 0.5
        radius = min(width * 0.2, height * 0.27, 170)
        if radius < 20:
            return

        for scale, tilt, depth, phase, speed in (
            (1.0, 0.34, 0.28, 0.0, 0.45),
            (0.82, 0.58, 0.16, 1.7, -0.32),
            (0.65, 0.25, 0.34, 3.2, 0.62),
        ):
            segments = []
            segment_count = 40
            for index in range(segment_count):
                shade = COLOR_ACCENT if index % 5 == 0 else COLOR_ACCENT_DIM
                segments.append(self.canvas.create_line(
                    0, 0, 0, 0, fill=shade,
                    width=2 if index % 5 == 0 else 1,
                    tags="reactor",
                ))
            node = self.canvas.create_oval(
                0, 0, 0, 0, fill=COLOR_ACCENT_GLOW,
                outline=COLOR_ACCENT, width=1, tags="reactor",
            )
            self._orbit_rings.append({
                "segments": segments, "node": node, "radius": radius * scale,
                "tilt": tilt, "depth": depth, "phase": phase, "speed": speed,
                "count": segment_count,
            })

        for scale, fill in (
            (0.34, "#06202a"),
            (0.27, "#07313d"),
            (0.19, "#0b1722"),
            (0.11, "#08738a"),
        ):
            glow_radius = radius * scale
            self._core_glow.append(self.canvas.create_oval(
                center_x - glow_radius, center_y - glow_radius,
                center_x + glow_radius, center_y + glow_radius,
                fill=fill, outline=COLOR_ACCENT_DIM, width=1, tags="reactor",
            ))
        self._core_center = self.canvas.create_oval(
            center_x - radius * 0.055, center_y - radius * 0.055,
            center_x + radius * 0.055, center_y + radius * 0.055,
            fill=COLOR_ACCENT_GLOW, outline="#d8fbff", width=2,
            tags="reactor",
        )
        self.canvas.create_text(
            center_x, center_y + radius * 1.2, text="NEURAL CORE  //  ONLINE",
            fill=COLOR_TEXT_SECONDARY, font=FONT_MONO_SMALL, tags="reactor",
        )

        self._update_orbits(center_x, center_y, radius)
        wraplength = max(180, int(self.chat_frame.winfo_width() * 0.72))
        for bubble in self._msg_bubbles:
            bubble.configure(wraplength=wraplength)

    def _update_orbits(self, center_x, center_y, radius):
        for orbit in self._orbit_rings:
            rotation = self._pulse_angle * orbit["speed"] + orbit["phase"]
            points = []
            for index in range(orbit["count"] + 1):
                angle = 2 * math.pi * index / orbit["count"] + rotation
                x = math.cos(angle) * orbit["radius"]
                y = math.sin(angle) * orbit["radius"] * orbit["tilt"]
                z = math.sin(angle + orbit["phase"]) * orbit["radius"] * orbit["depth"]
                x_rot = x * math.cos(rotation) - y * math.sin(rotation)
                y_rot = x * math.sin(rotation) + y * math.cos(rotation)
                perspective = 1 / max(0.55, 1 - z / (radius * 4))
                points.append((
                    center_x + x_rot * perspective,
                    center_y + y_rot * perspective,
                ))

            for index, item in enumerate(orbit["segments"]):
                self.canvas.coords(item, *points[index], *points[index + 1])

            node_index = int((self._frame_count * orbit["speed"] * 2) % orbit["count"])
            node_x, node_y = points[node_index]
            node_size = max(3, radius * 0.035)
            self.canvas.coords(
                orbit["node"], node_x - node_size, node_y - node_size,
                node_x + node_size, node_y + node_size,
            )

    def _animate(self):
        self._frame_count += 1
        self._pulse_angle += 0.05 * ANIMATION_SPEED if 'ANIMATION_SPEED' in dir() else 0.05

        # Update particles
        for p in self._particles:
            p.update()

        # Update voice ring
        if self._is_listening:
            pulse = 1 + 0.3 * math.sin(self._pulse_angle * 3)
            self.voice_ring.itemconfig(self._ring_fill, fill=COLOR_LISTENING)
            self.voice_ring.coords(
                self._ring_fill,
                20 + 5 * (1 - pulse), 20 + 5 * (1 - pulse),
                50 - 5 * (1 - pulse), 50 - 5 * (1 - pulse),
            )
        else:
            self.voice_ring.itemconfig(self._ring_fill, fill=COLOR_ACCENT)

        # Scan line
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self._scan_line_y += 4 * self._scan_direction
        if self._scan_line_y > height:
            self._scan_direction = -1
        elif self._scan_line_y < 0:
            self._scan_direction = 1
        self.canvas.delete("scan")
        self.canvas.create_rectangle(
            0, self._scan_line_y, width, self._scan_line_y + 2,
            fill=COLOR_ACCENT, outline="", tags="scan"
        )

        if self._orbit_rings:
            radius = min(width * 0.2, height * 0.27, 170)
            self._update_orbits(width / 2, height * 0.5, radius)
            if self._core_center:
                intensity = int(170 + 70 * (0.5 + 0.5 * math.sin(self._pulse_angle * 2)))
                self.canvas.itemconfig(
                    self._core_center,
                    fill=f"#{intensity:02x}ffff",
                )

        # Update clock
        now = time.strftime("%H:%M:%S")
        self.time_var.set(now)

        # Typing effect
        if self._typing_active and self._typing_index < len(self._typing_text):
            self._typing_index += 1
            if self._typing_bubble:
                self._typing_bubble.configure(
                    text=self._typing_text[: self._typing_index] + "▌"
                )
                self._scroll_chat()
            self.root.after(30, self._animate)
            return
        elif self._typing_active:
            self._typing_active = False
            if self._typing_bubble:
                self._typing_bubble.configure(text=self._typing_text)
                self._scroll_chat()
            self._typing_bubble = None

        self.root.after(30, self._animate)

    def _scroll_chat(self):
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    # ═══════════════════════════════════════════════════════════════════
    #  MESSAGE DISPLAY
    # ═══════════════════════════════════════════════════════════════════

    def _add_bubble(self, role: str, text: str, animate: bool = False):
        """Add a chat bubble with holographic styling."""
        color = COLOR_ACCENT if role == "jarvis" else COLOR_ACCENT_PURPLE
        label = JARVIS_NAME if role == "jarvis" else "You"
        anchor = "e" if role == "user" else "w"
        justify = "right" if role == "user" else "left"
        fg = COLOR_BG_SURFACE if role == "jarvis" else COLOR_BG_GLASS

        frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=6)

        bubble = ctk.CTkLabel(
            frame, text="" if animate else text, font=FONT_UI,
            text_color=COLOR_TEXT_PRIMARY, fg_color=fg,
            corner_radius=12, justify=justify,
            wraplength=max(180, int(self.chat_frame.winfo_width() * 0.72)),
        )
        bubble.pack(anchor=anchor, padx=8, pady=4)

        # Small label
        lbl = ctk.CTkLabel(
            frame, text=label, font=FONT_MONO_SMALL,
            text_color=color,
        )
        lbl.pack(anchor=anchor, padx=8)

        self._msg_bubbles.append(bubble)
        if animate:
            self._typing_bubble = bubble
        self._scroll_chat()

        # Add to activity log
        self._log_activity(role, text)

    def _log_activity(self, role: str, text: str):
        timestamp = time.strftime("%H:%M:%S")
        prefix = "▶" if role == "user" else "◀"
        color_tag = COLOR_ACCENT if role == "jarvis" else COLOR_ACCENT_PURPLE
        self.activity_log.insert(
            "end", f"[{timestamp}] {prefix} {text[:80]}\n",
        )
        self.activity_log.see("end")

    # ═══════════════════════════════════════════════════════════════════
    #  CALLBACKS & ACTIONS
    # ═══════════════════════════════════════════════════════════════════

    def _on_message(self, role: str, text: str):
        """Thread-safe callback from orchestrator."""
        self.root.after(0, self._add_bubble, role, text, role == "jarvis")
        self.root.after(0, self._update_status, text)

    def _update_status(self, text: str):
        self.status_var.set(f"Processing: {text[:60]}...")

    def _greet(self):
        greeting = f"Hello {USER_NAME}. {JARVIS_NAME} is online. All systems operational."
        self._add_bubble("jarvis", greeting)
        self.orch.tts.speak(greeting)
        self.status_var.set("Ready. Awaiting your command.")

    def _send_input(self):
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, "end")
        # Orchestrator callback (_on_message -> _add_bubble) handles the UI bubble
        threading.Thread(
            target=self._process_async, args=(text,), daemon=True
        ).start()

    def _send_command(self, cmd: str):
        self.input_entry.delete(0, "end")
        # Orchestrator callback handles the UI bubble
        threading.Thread(
            target=self._process_async, args=(cmd,), daemon=True
        ).start()

    def _process_async(self, text: str):
        response = self.orch.process_sync(text)
        # Trigger typing effect
        self.root.after(0, self._type_text, response)

    def _type_text(self, text: str):
        self._typing_text = text
        self._typing_index = 0
        self._typing_active = True
        if self._typing_bubble is None and self._msg_bubbles:
            self._typing_bubble = self._msg_bubbles[-1]
        self.root.after(30, self._animate)

    def _toggle_mic(self):
        if self._is_listening:
            self._is_listening = False
            self.mic_btn.configure(fg_color=COLOR_ACCENT_PURPLE, text="🎤")
            self.status_var.set("Microphone stopped.")
        else:
            if not self.orch.stt.is_available:
                self.status_var.set("Microphone unavailable — PyAudio not installed.")
                return
            self._is_listening = True
            self.mic_btn.configure(fg_color=COLOR_ERROR, text="⏹")
            self.status_var.set("Listening…")
            threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        while self._is_listening:
            try:
                text = self.orch.stt.listen()
                if text:
                    self.root.after(0, self._send_command, text)
            except Exception:
                pass

    def _on_close(self):
        self.orch.shutdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
