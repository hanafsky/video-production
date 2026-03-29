# Video Production

Automated post-production pipeline for coding screencasts and YouTube content.

Local Whisper transcription → Japanese filler removal (with Silero VAD) → EDL/SRT generation → DaVinci Resolve MCP integration.

## Prerequisites

- macOS + Apple Silicon (24 GB recommended)
- Python 3.10–3.12
- DaVinci Resolve Studio 18.5+
- ffmpeg

```bash
pip install openai-whisper opentimelineio srt torch
brew install ffmpeg
```

## Quick Start

### 1. Scaffold a project

```bash
bash skills/templates/project_structure.sh "MyVideo"
```

### 2. Extract audio

```bash
ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav
```

### 3. Transcribe with Whisper

```python
import whisper, json

model = whisper.load_model("large-v3")
result = model.transcribe("audio/audio.wav", language="ja", word_timestamps=True)

with open("transcripts/transcript.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### 4. Detect and remove fillers

```bash
python skills/scripts/detect_fillers.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

### 5. Generate EDL

```bash
python skills/scripts/generate_edl.py transcripts/clean_segments.json \
    --source raw/input.mov \
    --output edl/clean_edit.edl \
    --fps 24
```

### 6. Import into DaVinci Resolve

Import the EDL via Resolve MCP or manually.

## Project Structure

```
skills/
├── SKILL.md                  # Claude Code skill definition
├── scripts/
│   ├── detect_fillers.py     # Filler detection with Silero VAD
│   ├── generate_edl.py       # CMX 3600 EDL generation
│   └── optimize_srt.py       # SRT optimization
├── references/
│   ├── whisper_tips.md       # Whisper tips for Japanese
│   └── resolve_mcp_commands.md
└── templates/
    └── project_structure.sh  # Project scaffolding
```

Each video project follows this layout:

```
<ProjectName>_<YYYY-MM-DD>/
├── raw/            # Source recordings
├── audio/          # Extracted audio (mono 16 kHz PCM)
├── transcripts/    # Whisper output + filler analysis
├── edl/            # Generated EDL files
├── subtitles/      # Optimized SRT files
└── exports/        # Final rendered output
```

## License

MIT
