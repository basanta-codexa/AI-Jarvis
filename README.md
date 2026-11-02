# J.A.R.V.I.S. — Personal AI Assistant

J.A.R.V.I.S. is a Python desktop assistant with a dark, animated HUD, text and optional voice interaction, conversational AI, desktop commands, and persistent memory.

The application entry point is `main.py`. The actively used implementation is in `src/ai_jarvis/`.

## Features

- CustomTkinter desktop interface with an animated reactor, conversation view, quick commands, and activity panel.
- Optional AI responses through OpenAI-compatible providers, including OpenAI, OpenRouter, Grok, and Groq.
- Offline fallback responses when no API key is configured or a hosted AI request fails.
- Built-in skills for system information, approved app and website shortcuts, browser-based web search, and memory.
- Conversation history stored locally as JSON. Semantic memory uses ChromaDB and sentence-transformers when available.
- Windows text-to-speech through PowerShell System.Speech.
- Optional microphone input through SpeechRecognition and PyAudio.
- Command-line mode for text-based interaction.

## Requirements

- Python 3.10 or later.
- Windows is recommended. The GUI is built with CustomTkinter; the included TTS backend uses Windows PowerShell System.Speech.
- Internet access is needed for hosted AI providers, browser-based web search, Google speech recognition, and downloading the embedding model on first use.
- Microphone input requires a working microphone and PyAudio. PyAudio is optional and is not installed by the project dependencies; text interaction remains available without it.
- ChromaDB or embedding-model initialization may be unavailable on some systems; memory then falls back to basic in-memory notes.

## Quick start

Open PowerShell in the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
```

Alternatively, install the same runtime dependencies with:

```powershell
python -m pip install -r requirements.txt
```

Edit `.env` to set your name and, if desired, an AI provider and API key. Then launch the application:

```powershell
python main.py
```

To use the command-line interface instead:

```powershell
python main.py --cli
```

The first launch may take longer while sentence-transformers downloads its embedding model. If microphone support is unavailable, use the text input or CLI.

## Configuration

Settings are loaded from `.env` in the project root. Common options:

| Variable | Description | Default |
|---|---|---|
| `USER_NAME` | Name used in assistant greetings | `Sir` |
| `AI_PROVIDER` | Provider: `openai`, `openrouter`, `grok`, or `groq` | `openai` |
| `OPENAI_API_KEY` | API key for the selected provider | Empty |
| `AI_MODEL` | Model identifier accepted by the provider | `gpt-3.5-turbo` |
| `AI_TEMPERATURE` | Response creativity setting | `0.7` |
| `AI_MAX_TOKENS` | Maximum generated response tokens | `600` |

Provider credentials are private: keep them in `.env`, never commit them, and rotate any key that has been exposed. Without an API key, J.A.R.V.I.S. can still handle built-in commands and use its offline fallback.

## Example commands

- `What time is it?`
- `System status`
- `Open Notepad`
- `Search for Python tutorials`
- `Remember that I prefer concise answers`
- `What do you remember?`

Available commands depend on the loaded skills and the operating system.

## Project layout

```text
main.py                    Application entry point (GUI or CLI)
src/ai_jarvis/
  config/                  Application and provider settings
  core/                    Orchestration, plugins, and memory
  skills/                  AI, system, web, and memory skills
  ui/                      CustomTkinter interface
  voice/                   Speech recognition and text-to-speech
tests/                     Automated core behavior tests
requirements.txt           Installs runtime dependencies from pyproject.toml
pyproject.toml             Package metadata and development dependencies
```

`pyproject.toml` is the single source of truth for runtime dependencies. `requirements.txt` delegates to it so the two installation methods stay consistent.

Runtime data, including conversation history and the local vector database, is stored under `data/` and is intentionally excluded from version control.

## Development

Install the optional development tools with:

```powershell
python -m pip install -e ".[dev]"
```

Run the automated tests with:

```powershell
python -m pytest
```

