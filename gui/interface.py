# ──────────────────────────────────────────────────────────────────────────────
#  gui/interface.py  –  Futuristic JARVIS desktop UI (CustomTkinter)
# ──────────────────────────────────────────────────────────────────────────────
"""
Phase 5 UI features:
  • Arc-reactor pulsing ring animation (canvas)
  • Conversation history scroll with colour-coded bubbles + timestamps
  • Live status bar  (AI | Voice | Memory indicators)
  • Text input with send button
  • Microphone toggle button
  • Settings panel (voice rate, volume, theme)
  • System tray support (minimize to background)
  • Quick commands sidebar
"""
import threading
import tkinter as tk
from tkinter import font as tkfont
import customtkinter as ctk
from config import settings


ctk.set_appearance_mode(settings.THEME)
ctk.set_default_color_theme("blue")


# ── Colour tokens ─────────────────────────────────────────────────────────────
BG         = settings.COLOR_BG
SURFACE    = settings.COLOR_SURFACE
ACCENT     = settings.COLOR_ACCENT
ACCENT2    = settings.COLOR_ACCENT2
TEXT       = settings.COLOR_TEXT
TEXT_DIM   = settings.COLOR_TEXT_DIM
C_USER     = settings.COLOR_USER
C_JARVIS   = settings.COLOR_JARVIS
C_SYSTEM   = "#a78bfa"
C_ERROR    = settings.COLOR_ERROR


class JarvisGUI:
    """Main GUI window."""

    def __init__(self, jarvis):
        """
        Args:
            jarvis: A core.Jarvis instance.  The GUI replaces its
                    on_message callback so messages flow into the UI.
        """
        self.jarvis = jarvis
        self.jarvis.on_message = self._on_message   # wire callback

        self.root = ctk.CTk()
        self.root.title(settings.WINDOW_TITLE)
        self.root.geometry(f"{settings.WINDOW_WIDTH}x{settings.WINDOW_HEIGHT}")
        self.root.configure(fg_color=BG)
        self.root.resizable(True, True)
        self.root.minsize(700, 500)

        # Handle window close – hide to tray instead of quitting
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        # Tray availability must be set before UI builds (badges reference it)
        self._tray_icon = None
        self._tray_available = False
        self._init_tray()

        self._build_ui()
        self._start_pulse_animation()

        # Greet on open (non-blocking)
        self.root.after(500, lambda: threading.Thread(
            target=self.jarvis.speak,
            args=(f"Hello {settings.USER_NAME}. All systems online. How can I help?",),
            daemon=True,
        ).start())

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_header()
        self._build_main()
        self._build_input()
        self._build_statusbar()

    # Header ──────────────────────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color=SURFACE, corner_radius=0, height=90)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Animated arc-reactor canvas
        self.canvas = tk.Canvas(header, width=70, height=70, bg=SURFACE,
                                highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=(15, 10), pady=10)
        self._arc_rings = []
        self._pulse_radius = 15
        self._pulse_growing = True
        self._draw_reactor()

        # Title block
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            title_frame, text="J.A.R.V.I.S.",
            font=ctk.CTkFont(family="Courier New", size=30, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Just A Rather Very Intelligent System  •  Personal AI Assistant",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_DIM,
        ).pack(anchor="w")

        # Header buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=15)

        self.settings_btn = ctk.CTkButton(
            btn_frame, text="⚙ Settings", width=100, height=32,
            fg_color=ACCENT2, hover_color="#6d28d9",
            command=self._open_settings,
        )
        self.settings_btn.pack(pady=5)

    # Main layout ─────────────────────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 0))
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_chat(main)
        self._build_sidebar(main)

    # Chat panel ──────────────────────────────────────────────────────────────

    def _build_chat(self, parent):
        chat_frame = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12)
        chat_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.columnconfigure(0, weight=1)

        # Scrollable chat area
        self.chat_scroll = ctk.CTkScrollableFrame(
            chat_frame, fg_color="transparent", corner_radius=0,
        )
        self.chat_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_scroll.columnconfigure(0, weight=1)

        self._msg_row = 0  # tracks next row in chat grid

    # Sidebar ─────────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12, width=240)
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.grid_propagate(False)

        # Section: Quick Commands
        ctk.CTkLabel(
            sidebar, text="⚡ Quick Commands",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).pack(padx=10, pady=(15, 8), anchor="w")

        quick_cmds = [
            ("🕐 Time", "what time is it"),
            ("📅 Date", "what is today's date"),
            ("🤖 Who are you?", "who are you"),
            ("🧠 Help", "help"),
            ("📋 System Status", "system status"),
            ("😄 Tell me a joke", "tell me a joke"),
            ("📝 My Notes", "what do you remember"),
            ("🌐 Open Google", "open google"),
            ("▶️ Open YouTube", "open youtube"),
            ("💻 Open Notepad", "open notepad"),
        ]
        for label, cmd in quick_cmds:
            ctk.CTkButton(
                sidebar, text=label, anchor="w",
                fg_color="transparent", hover_color=ACCENT2,
                border_color=ACCENT2, border_width=1,
                height=34, command=lambda c=cmd: self._send_command(c),
            ).pack(fill="x", padx=10, pady=2)

        # Section: Notes
        ctk.CTkLabel(
            sidebar, text="📌 Remember",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).pack(padx=10, pady=(20, 5), anchor="w")

        self.note_entry = ctk.CTkEntry(
            sidebar, placeholder_text="Type a note…",
            fg_color=BG, border_color=ACCENT2,
        )
        self.note_entry.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkButton(
            sidebar, text="💾 Save Note", height=34,
            fg_color=ACCENT2, hover_color="#6d28d9",
            command=self._save_note,
        ).pack(fill="x", padx=10)

        # Stats
        self.stats_label = ctk.CTkLabel(
            sidebar, text="", font=ctk.CTkFont(size=11),
            text_color=TEXT_DIM, justify="left",
        )
        self.stats_label.pack(padx=10, pady=(20, 0), anchor="w")
        self._update_stats()

    # Input bar ───────────────────────────────────────────────────────────────

    def _build_input(self):
        bar = ctk.CTkFrame(self.root, fg_color=SURFACE, corner_radius=0, height=70)
        bar.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        bar.columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        # Mic button
        self.mic_btn = ctk.CTkButton(
            bar, text="🎤", width=50, height=46,
            fg_color=ACCENT2, hover_color="#6d28d9", corner_radius=25,
            command=self._toggle_mic,
            state="normal" if self.jarvis.stt.is_available else "disabled",
        )
        self.mic_btn.grid(row=0, column=0, padx=(12, 6), pady=12)

        # Mic status hint (shown when mic unavailable)
        if not self.jarvis.stt.is_available:
            self.mic_hint = ctk.CTkLabel(
                bar, text="Mic unavailable (PyAudio missing)",
                font=ctk.CTkFont(size=9), text_color=TEXT_DIM,
            )
            self.mic_hint.grid(row=0, column=0, padx=(12, 6), pady=(58, 0), sticky="w")
        else:
            self.mic_hint = None

        # Text entry
        self.input_entry = ctk.CTkEntry(
            bar,
            placeholder_text=f"Ask {settings.JARVIS_NAME} anything…",
            font=ctk.CTkFont(size=14),
            height=46, corner_radius=23,
            fg_color=BG, border_color=ACCENT,
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=12)
        self.input_entry.bind("<Return>", lambda e: self._send_input())

        # Send button
        ctk.CTkButton(
            bar, text="Send ▶", width=90, height=46,
            fg_color=ACCENT, hover_color="#0891b2",
            text_color=BG, font=ctk.CTkFont(weight="bold"),
            corner_radius=23, command=self._send_input,
        ).grid(row=0, column=2, padx=(6, 12), pady=12)

    # Status bar ──────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = ctk.CTkFrame(self.root, fg_color=BG, height=26, corner_radius=0)
        sb.grid(row=3, column=0, sticky="ew")
        sb.columnconfigure(4, weight=1)

        self.ai_badge = self._status_badge(sb, "🧠 AI", 0)
        self.mic_badge = self._status_badge(sb, "🎤 Voice", 1)
        self.mem_badge = self._status_badge(sb, "💾 Memory", 2)
        self.tray_badge = self._status_badge(sb, "📭 Tray", 3)
        self.status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(
            sb, textvariable=self.status_var,
            font=ctk.CTkFont(size=10), text_color=TEXT_DIM,
        ).grid(row=0, column=4, padx=10, sticky="e")

        self._refresh_badges()

    @staticmethod
    def _status_badge(parent, text, col):
        lbl = ctk.CTkLabel(
            parent, text=text, font=ctk.CTkFont(size=10),
            text_color=TEXT_DIM, padx=8,
        )
        lbl.grid(row=0, column=col, padx=(4, 0), sticky="w")
        return lbl

    # ── System tray ─────────────────────────────────────────────────────

    def _init_tray(self):
        try:
            import pystray
            from PIL import Image
            # Create a simple icon image
            image = Image.new("RGB", (64, 64), color=(0, 212, 255))
            self._tray_available = True
        except Exception:
            self._tray_available = False

    def _hide_to_tray(self):
        """Hide window to system tray instead of closing."""
        if self._tray_available:
            self.root.withdraw()
            self.status_var.set("Minimized to tray.")
        else:
            self.root.destroy()

    def _restore_from_tray(self):
        """Restore window from system tray."""
        self.root.deiconify()
        self.status_var.set("Ready.")

    # ── Pulsing reactor animation ─────────────────────────────────────────────

    def _draw_reactor(self):
        cx, cy, r = 35, 35, 28
        # Outer glow rings
        for i, alpha in enumerate([0.15, 0.30, 0.55, 1.0]):
            ri = r - i * 6
            col = ACCENT
            self.canvas.create_oval(cx - ri, cy - ri, cx + ri, cy + ri,
                                    outline=col, width=1)
        # Inner core circle
        self._core = self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10,
                                              fill=ACCENT, outline="")
        # Pulse ring (animated)
        pr = self._pulse_radius
        self._pulse_ring = self.canvas.create_oval(cx - pr, cy - pr, cx + pr, cy + pr,
                                                    outline=ACCENT, width=2)

    def _start_pulse_animation(self):
        self.root.after(50, self._animate_pulse)

    def _animate_pulse(self):
        cx, cy = 35, 35
        pr = self._pulse_radius

        if self._pulse_growing:
            pr += 0.8
            if pr >= 30:
                self._pulse_growing = False
        else:
            pr -= 0.8
            if pr <= 12:
                self._pulse_growing = True

        self._pulse_radius = pr
        self.canvas.coords(self._pulse_ring, cx - pr, cy - pr, cx + pr, cy + pr)

        # Change core colour while listening
        if self.jarvis.listening:
            self.canvas.itemconfig(self._core, fill="#ef4444")
        else:
            self.canvas.itemconfig(self._core, fill=ACCENT)

        self.root.after(50, self._animate_pulse)

    # ── Message handling ──────────────────────────────────────────────────────

    def _on_message(self, role: str, text: str):
        """Called by Jarvis subsystem to push messages to the UI (thread-safe)."""
        self.root.after(0, self._add_bubble, role, text)

    def _add_bubble(self, role: str, text: str):
        """Add a chat bubble to the scrollable chat area."""
        colour_map = {
            "user": C_USER,
            "jarvis": C_JARVIS,
            "system": C_SYSTEM,
            "error": C_ERROR,
        }
        label_map = {
            "user": "You",
            "jarvis": "JARVIS",
            "system": "System",
            "error": "Error",
        }
        colour = colour_map.get(role, TEXT_DIM)
        anchor = "e" if role == "user" else "w"
        label = label_map.get(role, role.title())

        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M")

        row_frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        row_frame.grid(row=self._msg_row, column=0, sticky="ew", pady=3, padx=4)
        row_frame.columnconfigure(0, weight=1)

        bubble = ctk.CTkFrame(
            row_frame,
            fg_color=SURFACE,
            corner_radius=12,
            border_color=colour, border_width=1,
        )
        bubble.grid(row=0, column=0, sticky=anchor, padx=4)

        # Header with label + timestamp
        header_frame = ctk.CTkFrame(bubble, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(6, 0))
        header_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame, text=label,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=colour,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header_frame, text=timestamp,
            font=ctk.CTkFont(size=9),
            text_color=TEXT_DIM,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            bubble, text=text,
            font=ctk.CTkFont(size=13),
            text_color=TEXT,
            wraplength=600,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        self._msg_row += 1
        self.root.update_idletasks()

        # Auto-scroll to bottom
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

        # Update status bar
        self.status_var.set(f"{label}: {text[:60]}{'…' if len(text) > 60 else ''}")
        self._update_stats()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _send_input(self):
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, "end")
        threading.Thread(target=self.jarvis.process_text, args=(text,), daemon=True).start()

    def _send_command(self, cmd: str):
        threading.Thread(target=self.jarvis.process_text, args=(cmd,), daemon=True).start()

    def _toggle_mic(self):
        if not self.jarvis.stt.is_available:
            return  # Mic not available
        if self.jarvis.listening:
            self.jarvis.stop_listening()
            self.mic_btn.configure(fg_color=ACCENT2, text="🎤")
        else:
            self.jarvis.start_listening()
            self.mic_btn.configure(fg_color=C_ERROR, text="⏹ Stop")
        self._refresh_badges()

    def _save_note(self):
        note = self.note_entry.get().strip()
        if note:
            self.note_entry.delete(0, "end")
            threading.Thread(
                target=self.jarvis.process_text,
                args=(f"remember {note}",),
                daemon=True,
            ).start()

    # ── Settings panel ────────────────────────────────────────────────────────

    def _open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Settings")
        win.geometry("400x520")
        win.configure(fg_color=SURFACE)
        win.grab_set()

        ctk.CTkLabel(
            win, text="⚙ Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=ACCENT,
        ).pack(pady=(20, 15))

        # Voice rate
        ctk.CTkLabel(win, text=f"Speech Rate: {settings.TTS_RATE} wpm",
                     text_color=TEXT).pack(anchor="w", padx=20)
        rate_slider = ctk.CTkSlider(win, from_=100, to=250,
                                    button_color=ACCENT,
                                    command=lambda v: self._set_rate(int(v), rate_lbl))
        rate_slider.set(settings.TTS_RATE)
        rate_slider.pack(fill="x", padx=20, pady=4)
        rate_lbl = ctk.CTkLabel(win, text=f"{settings.TTS_RATE} wpm", text_color=TEXT_DIM)
        rate_lbl.pack(anchor="w", padx=20)

        # Volume
        ctk.CTkLabel(win, text="Volume:", text_color=TEXT).pack(anchor="w", padx=20, pady=(12, 0))
        vol_slider = ctk.CTkSlider(win, from_=0.0, to=1.0,
                                   button_color=ACCENT,
                                   command=lambda v: self.jarvis.tts.set_volume(v))
        vol_slider.set(settings.TTS_VOLUME)
        vol_slider.pack(fill="x", padx=20, pady=4)

        # Theme
        ctk.CTkLabel(win, text="Theme:", text_color=TEXT).pack(anchor="w", padx=20, pady=(12, 0))
        theme_menu = ctk.CTkOptionMenu(
            win, values=["dark", "light", "system"],
            command=lambda t: ctk.set_appearance_mode(t),
            fg_color=ACCENT2,
        )
        theme_menu.set(settings.THEME)
        theme_menu.pack(fill="x", padx=20, pady=4)

        # Clear history
        ctk.CTkButton(
            win, text="🗑 Clear Conversation",
            fg_color=C_ERROR, hover_color="#b91c1c",
            command=self._clear_chat,
        ).pack(fill="x", padx=20, pady=(30, 5))

        ctk.CTkButton(win, text="Close", fg_color=ACCENT2,
                      command=win.destroy).pack(fill="x", padx=20)

    def _set_rate(self, rate: int, label):
        settings.TTS_RATE = rate
        self.jarvis.tts.set_rate(rate)
        label.configure(text=f"{rate} wpm")

    def _clear_chat(self):
        for widget in self.chat_scroll.winfo_children():
            widget.destroy()
        self._msg_row = 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_badges(self):
        ai_ok = self.jarvis.brain.is_available
        mic_ok = self.jarvis.stt.is_available
        self.ai_badge.configure(text_color=ACCENT if ai_ok else TEXT_DIM)
        self.mic_badge.configure(text_color=C_JARVIS if self.jarvis.listening else
                                 (ACCENT if mic_ok else TEXT_DIM))
        self.mem_badge.configure(text_color=ACCENT)
        self.tray_badge.configure(text_color=ACCENT if self._tray_available else TEXT_DIM)

        # Update mic hint text if mic is unavailable
        if self.mic_hint and mic_ok:
            self.mic_hint.destroy()
            self.mic_hint = None

    def _update_stats(self):
        stats = self.jarvis.memory.get_stats()
        self.stats_label.configure(
            text=(f"💬 {stats['total_messages']} messages\n"
                  f"📌 {stats['total_notes']} notes")
        )

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
