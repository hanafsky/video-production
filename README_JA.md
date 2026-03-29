# Video Production

撮影した動画から「えーと」「あのー」などの**フィラー（つなぎ言葉）を自動で見つけてカット編集を生成する**ツールです。コーディング動画やYouTubeコンテンツのポストプロダクションを効率化します。

## インストール

```bash
npx skills add hanafsky/video-post-production
```

## できること

- **文字起こし** — Whisperを使って動画の音声をローカルで文字起こし（日本語・英語対応）
- **フィラー自動検出** — 「えーと」「あのー」「um」「uh」などの不要な言い回しをAIが検出。Silero VADで無音区間も考慮し、誤検出を抑えます
- **カット編集の自動生成** — フィラーを除いたEDL（編集リスト）やSRT（字幕）を出力
- **DaVinci Resolve連携** — 生成したEDLをResolveに直接インポート可能（MCP経由または手動）

## 必要なもの

- macOS + Apple Silicon（メモリ24 GB 推奨）
- Python 3.10〜3.12
- DaVinci Resolve Studio 18.5+
- ffmpeg

```bash
pip install openai-whisper opentimelineio srt torch
brew install ffmpeg
```

## 使い方

### 1. プロジェクトのひな形を作る

```bash
bash skills/templates/project_structure.sh "MyVideo"
```

### 2. 動画から音声を抽出する

```bash
ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav
```

### 3. Whisperで文字起こしする

```python
import whisper, json

model = whisper.load_model("large-v3")
result = model.transcribe("audio/audio.wav", language="ja", word_timestamps=True)

with open("transcripts/transcript.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### 4. フィラーを検出・除去する

**日本語の場合:**

```bash
python skills/scripts/detect_fillers.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

**英語の場合:**

```bash
python skills/scripts/detect_fillers_en.py transcripts/transcript.json \
    --wav audio/audio.wav \
    --output transcripts/clean_segments.json
```

### 5. EDLを生成する

```bash
python skills/scripts/generate_edl.py transcripts/clean_segments.json \
    --source raw/input.mov \
    --output edl/clean_edit.edl \
    --fps 24
```

### 6. DaVinci Resolveにインポートする

Resolve MCP経由、または手動でEDLをインポートしてください。

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
    └── project_structure.sh  # プロジェクトひな形作成
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
