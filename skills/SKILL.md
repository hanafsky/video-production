---
name: video-production
description: |
  Video production automation skill. Integrates local Whisper transcription,
  Japanese filler-word detection/removal with Silero VAD, EDL/SRT generation,
  and DaVinci Resolve MCP control. Streamlines the post-production pipeline
  for coding screencasts (devaslife-style) and YouTube content.
  Use this skill when the user mentions: video editing, filler removal,
  transcription, Whisper, EDL, SRT, subtitles, DaVinci Resolve, Resolve MCP,
  timeline, color grading, rendering, or any recording/editing/publishing task.
  Also trigger when the user wants to automate post-production workflows,
  remove silence/filler from recordings, or generate subtitles from audio.
---

# Video Production Skill

Automates the post-production pipeline:
Whisper (local) + Claude Code + DaVinci Resolve MCP.
Recording → Transcription → Filler removal → Timeline → Effects → Subtitles → Render.

## Prerequisites

- **macOS + Apple Silicon** (24 GB Unified Memory — can run large-v3)
- **DaVinci Resolve Studio 18.5+** (free version lacks external scripting)
- **Python 3.10–3.12**
- **DaVinci Resolve MCP** configured in Claude Code

## Required Packages (first-time setup)

```bash
pip install openai-whisper opentimelineio srt torch
# ffmpeg is also required on macOS
brew install ffmpeg
```

> Packages must be installed by the human. The AI presents the commands and waits.

## Core Rules

### 1. Transcription runs locally with Whisper

No API key required. Audio never leaves the machine.

```python
import whisper
model = whisper.load_model("large-v3")  # OK for 24 GB Mac
result = model.transcribe("audio.wav", language="ja", word_timestamps=True)
```

**Model selection guide:**
- `medium` — fast, reasonable accuracy. Try first.
- `large-v3` — highest accuracy for Japanese. Needs 24 GB.
- `turbo` — optimized for English. Not recommended for Japanese.

### 2. Filler detection uses `scripts/detect_fillers.py`

Detects Japanese fillers from Whisper's word-level timestamps, corrects
boundaries with Silero VAD + energy analysis.

### 3. EDL generation uses `scripts/generate_edl.py`

Produces a CMX 3600 EDL from clean segments. Importable by DaVinci Resolve.

### 4. DaVinci Resolve is controlled via MCP

All Resolve operations go through MCP tools. Never use the Python API directly.

### 5. SRT optimization uses `scripts/optimize_srt.py`

Cleans up Whisper's raw SRT: fixes mis-conversions, adjusts line length
(≤ 20 chars/line), merges short cues, removes fillers.

## Project Directory Layout

Each video project gets its own directory with **separate folders per artifact type**.
Use `templates/project_structure.sh` to scaffold a new project.

```
<ProjectName>_<YYYY-MM-DD>/
├── raw/            # Source recordings (.mov, .mp4)
├── audio/          # Extracted audio (.wav) — mono 16 kHz PCM
├── transcripts/    # Whisper output + filler analysis
│   ├── transcript.json       # Raw Whisper JSON (word_timestamps)
│   ├── clean_segments.json   # After filler removal
│   └── fillers_report.txt    # Filler log for human review
├── edl/            # Generated EDL files
│   └── clean_edit.edl
├── subtitles/      # Optimized SRT files
│   └── subtitles.srt
└── exports/        # Final rendered output
    └── final_output.mp4
```

**Important:** Always write intermediate outputs to the correct subfolder.
Never dump transcripts, EDLs, or SRTs into the project root.

## Workflow

### Phase 1: Audio Extraction

Extract audio from video via DaVinci Resolve MCP or ffmpeg:

```bash
ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav
```

Key: **Mono, 16 kHz, Linear PCM** is optimal for Whisper.

### Phase 2: Transcription

```python
import whisper, json

model = whisper.load_model("large-v3")
result = model.transcribe(
    "audio/audio.wav",
    language="ja",
    word_timestamps=True,
    verbose=False,
)

with open("transcripts/transcript.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### Phase 3: Filler Detection & Removal

```bash
python scripts/detect_fillers.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

Output:
- `transcripts/clean_segments.json` — segments with fillers cut
- Console report showing detected fillers and timestamp corrections

**Important:** Review the filler report before proceeding. Prefer human
verification over full automation.

### Phase 4: EDL Generation

```bash
python scripts/generate_edl.py transcripts/clean_segments.json \
    --source raw/input.mov \
    --output edl/clean_edit.edl \
    --fps 24
```

### Phase 5: Import into Resolve (MCP)

```
MCP operations:
1. create_timeline("CleanCut")
2. Import EDL via MCP timeline tools
3. open_page("edit") to verify
```

Resolve EDL import setting:
- Project Settings → Conform Options → "Assist using reel names from: Source clip filename"

### Phase 6: Effects & Color Grading (MCP)

```
MCP examples:
- open_page("color")
- add_color_node() on each clip
- fusion_comp for titles/text
- set_clip_property() for transforms
```

### Phase 7: Subtitle Generation

```bash
python scripts/optimize_srt.py transcripts/transcript.json \
    --output subtitles/subtitles.srt
```

### Phase 8: Render & Export

```
MCP operations:
- open_page("deliver")
- Configure render settings (H.265 4K YouTube preset, etc.)
- render_project()
```

## Common Pitfalls

| Situation | Wrong approach | Correct approach |
|-----------|---------------|-----------------|
| Whisper converts "えー" to kanji | Ignore it | Use broad regex patterns in filler detection |
| Long silence causes hallucination | Switch models | Try `--condition_on_previous_text False` |
| EDL timecode drift | Manual fix | Verify fps matches the source |
| Resolve not responding via MCP | Retry blindly | Confirm Resolve is running + External scripting enabled |
| Filler removal deletes real content | Trust full automation | Human reviews filler report first |

## Reference

- `scripts/detect_fillers.py` — Japanese filler detection with VAD correction
- `scripts/generate_edl.py` — Clean segments → CMX 3600 EDL
- `scripts/optimize_srt.py` — SRT optimization
- `references/whisper_tips.md` — Whisper tips for Japanese
- `references/resolve_mcp_commands.md` — Common MCP commands
- `templates/project_structure.sh` — Project directory scaffolding
