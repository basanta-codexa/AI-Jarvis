# ──────────────────────────────────────────────────────────────────────────────
#  main.py  –  AI JARVIS entry point
# ──────────────────────────────────────────────────────────────────────────────
"""
Usage:
    python main.py          → Launch the cinematic GUI  (default)
    python main.py --cli    → Run in terminal (no GUI)
    python main.py --help   → Show this help
"""
import sys
import os

# Ensure stdout can handle unicode
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

BANNER = r"""
   ___    _    ____  __     __ ___  ____
  |_ _|  / \  |  _ \ \ \   / /|_ _|/ ___|
   | |  / _ \ | |_) | \ \ / /  | | \___ \
   | | / ___ \|  _ <   \ V /   | |  ___) |
  |___/_/   \_\_| \_\   \_/   |___||____/

  J.A.R.V.I.S. — Neural Interface v2.0
  Just A Rather Very Intelligent System
"""


def launch_gui():
    print(BANNER)
    print("  Initializing neural interface…\n")
    from ai_jarvis.core.orchestrator import JarvisOrchestrator
    from ai_jarvis.ui.gui import JarvisGUI

    orch = JarvisOrchestrator()
    gui = JarvisGUI(orch)
    gui.run()


def launch_cli():
    print(BANNER)
    from ai_jarvis.core.orchestrator import JarvisOrchestrator

    orch = JarvisOrchestrator()

    def on_message(role, text):
        prefix = {
            "user": f"\n  {USER_NAME if False else 'You'}",
            "jarvis": f"\n  JARVIS",
            "system": "  [System]",
            "error": "  [Error]",
        }.get(role, f"  [{role}]")
        print(f"{prefix}: {text}")

    orch.on_message = on_message
    print("  Type a command (or 'exit' to quit)\n")

    from ai_jarvis.config.settings import USER_NAME

    while True:
        try:
            cmd = input("  You: ").strip()
            if not cmd:
                continue
            orch.process_sync(cmd)
            if getattr(orch, "request_shutdown", False) or cmd.lower() in (
                "exit", "quit", "shutdown", "bye", "goodbye",
            ):
                break
        except (KeyboardInterrupt, EOFError):
            orch.tts.speak("Goodbye!")
            break

    orch.shutdown()


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    elif "--cli" in args:
        launch_cli()
    else:
        launch_gui()
