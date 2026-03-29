# Video Production

コーディング動画・YouTubeコンテンツ向けの動画制作自動化パイプライン。

ローカルWhisper文字起こし → フィラー除去（日本語・英語対応、Silero VAD補正） → EDL/SRT生成 → DaVinci Resolve MCP連携。

## 前提環境

- macOS + Apple Silicon（24 GB 推奨）
- Python 3.10〜3.12
- DaVinci Resolve Studio 18.5+
- ffmpeg

```bash
pip install openai-whisper opentimelineio srt torch
brew install ffmpeg
```

## クイックスタート

### 1. プロジェクト作成

```bash
bash skills/templates/project_structure.sh "MyVideo"
```

### 2. 音声抽出

```bash
ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav
```

### 3. Whisperで文字起こし

```python
import whisper, json

model = whisper.load_model("large-v3")
result = model.transcribe("audio/audio.wav", language="ja", word_timestamps=True)

with open("transcripts/transcript.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### 4. フィラー検出・除去

**日本語:**

```bash
python skills/scripts/detect_fillers.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

**英語:**

```bash
python skills/scripts/detect_fillers_en.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

### 5. EDL生成

```bash
python skills/scripts/generate_edl.py transcripts/clean_segments.json \
    --source raw/input.mov \
    --output edl/clean_edit.edl \
    --fps 24
```

### 6. DaVinci Resolveにインポート

Resolve MCP経由またはマニュアルでEDLをインポート。

## プロジェクト構成

```
skills/
├── SKILL.md                  # Claude Code スキル定義
├── scripts/
│   ├── detect_fillers.py     # 日本語フィラー検出（Silero VAD補正付き）
│   ├── detect_fillers_en.py  # 英語フィラー検出（Silero VAD補正付き）
│   ├── generate_edl.py       # CMX 3600 EDL生成
│   └── optimize_srt.py       # SRT最適化
├── references/
│   ├── whisper_tips.md       # Whisper日本語運用Tips
│   └── resolve_mcp_commands.md
└── templates/
    └── project_structure.sh  # プロジェクト雛形作成
```

各動画プロジェクトのディレクトリ構成:

```
<プロジェクト名>_<YYYY-MM-DD>/
├── raw/            # 収録素材
├── audio/          # 抽出した音声（モノラル 16 kHz PCM）
├── transcripts/    # 文字起こし結果・フィラー解析
├── edl/            # 生成したEDL
├── subtitles/      # 最適化済みSRT
└── exports/        # 最終出力
```

## ライセンス

MIT
