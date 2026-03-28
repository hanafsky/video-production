---
name: video-production
description: |
  動画制作の自動化ワークフロースキル。Whisperによるローカル文字起こし、
  日本語フィラーワード検出・除去、EDL/SRT生成、DaVinci Resolve MCP連携を統合。
  devaslife風コーディング動画やYouTubeコンテンツの制作パイプラインを効率化する。
  Use this skill when the user mentions: 動画制作, 動画編集, video editing, フィラー除去,
  filler removal, 文字起こし, transcription, Whisper, EDL, SRT, 字幕,
  DaVinci Resolve, Resolve MCP, devaslife, YouTube動画, コーディング動画,
  タイムライン, timeline, カラーグレーディング, color grading, レンダリング,
  または動画の収録・編集・公開に関連する作業を行う場合。
  Also trigger when the user wants to automate post-production workflows,
  remove silence/filler from recordings, or generate subtitles from audio.
---

# Video Production Skill

動画制作パイプラインの自動化スキル。
Whisper（ローカル）+ Claude Code + DaVinci Resolve MCP で、
収録後の文字起こし → フィラー除去 → タイムライン生成 → エフェクト → 字幕 → レンダリング を効率化する。

## 前提環境

- **macOS + Apple Silicon**（24GB Unified Memory → large-v3 使用可）
- **DaVinci Resolve Studio 18.5+**（無料版は外部スクリプティング非対応）
- **Python 3.10〜3.12**
- **DaVinci Resolve MCP** が Claude Code に設定済み

## 必要パッケージ（初回セットアップ）

```bash
pip install openai-whisper opentimelineio srt
# macOS Apple Silicon の場合、ffmpeg も必要
brew install ffmpeg
```

⚠️ パッケージインストールは人間が行う。AIは上記コマンドを提示して待つ。

## 基本ルール

### 1. 文字起こしはローカルWhisperで行う

APIキー不要。音声データが外部に送信されない。

```python
import whisper
model = whisper.load_model("large-v3")  # 24GB Mac なら OK
result = model.transcribe("audio.wav", language="ja")
```

**モデル選択ガイド:**
- `medium` — 高速、精度そこそこ。まず試す
- `large-v3` — 高精度、日本語向き。24GB Mac推奨
- `turbo` — 英語最適化。日本語には非推奨

### 2. フィラー検出は scripts/detect_fillers.py を使う

詳細は `scripts/detect_fillers.py` を参照。
日本語フィラーのパターンリストとWhisperセグメントの解析ロジックを含む。

### 3. EDL生成は scripts/generate_edl.py を使う

フィラー除去後のセグメントからEDLファイルを生成。
DaVinci Resolve にインポート可能な CMX 3600 形式。

### 4. DaVinci Resolve MCP で操作する

Resolve の操作は MCP ツール経由で行う。直接 Python API は使わない。

### 5. SRT最適化は scripts/optimize_srt.py を使う

Whisperの生SRT出力を校正・整形して、YouTube/動画用に最適化。

## ワークフロー

### Phase 1: 音声抽出

DaVinci Resolve MCP でタイムラインからWAVをレンダリング、
または ffmpeg で動画ファイルから直接抽出：

```bash
ffmpeg -i input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

ポイント: **モノラル・16kHz・Linear PCM** が Whisper に最適。

### Phase 2: 文字起こし

```python
import whisper
import json

model = whisper.load_model("large-v3")
result = model.transcribe(
    "audio.wav",
    language="ja",
    word_timestamps=True,   # 単語レベルのタイムスタンプ
    verbose=False
)

# JSON保存（後続処理で使用）
with open("transcript.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### Phase 3: フィラー検出・除去

`scripts/detect_fillers.py` を実行：

```bash
python scripts/detect_fillers.py transcript.json --output clean_segments.json
```

出力:
- `clean_segments.json` — フィラー除去済みセグメント
- `fillers_report.txt` — 検出されたフィラーの一覧（レビュー用）

**重要:** フィラーレポートは人間が確認する。完全自動化より最終チェック推奨。

### Phase 4: EDL生成

```bash
python scripts/generate_edl.py clean_segments.json --fps 24 --output clean_edit.edl
```

### Phase 5: Resolve にインポート（MCP経由）

```
MCP操作:
1. create_timeline("CleanCut")
2. EDL をインポート（MCP の timeline ツール経由）
3. open_page("edit") で確認
```

ResolveへのEDLインポート時の設定:
- Project Settings → Conform Options → "Assist using reel names from: Source clip filename"

### Phase 6: エフェクト・カラグレ（MCP経由）

```
MCP操作例:
- open_page("color")
- add_color_node() で各クリップにノード追加
- fusion_comp でタイトル・テキスト追加
- set_clip_property() でトランスフォーム調整
```

### Phase 7: 字幕生成

```bash
python scripts/optimize_srt.py transcript.json --output subtitles.srt
```

最適化内容: 誤変換修正、行長調整（20文字/行）、短すぎる表示の結合、フィラー削除

### Phase 8: レンダリング＋公開素材

```
MCP操作:
- open_page("deliver")
- レンダリング設定（H.265 4K YouTube プリセット等）
- render_project() で開始
```

## ファイル配置規則

```
project/
├── raw/                    # 収録素材
│   └── recording_2026-03-28.mov
├── audio/
│   └── audio.wav           # 抽出した音声
├── transcripts/
│   ├── transcript.json     # Whisper生出力
│   ├── clean_segments.json # フィラー除去済み
│   └── fillers_report.txt  # フィラーレポート
├── edl/
│   └── clean_edit.edl      # 生成したEDL
├── subtitles/
│   └── subtitles.srt       # 最適化済みSRT
└── exports/
    └── final_output.mp4    # 最終出力
```

## よくある失敗パターン

| 状況 | 悪い対応 | 正しい対応 |
|------|----------|------------|
| Whisperが「えー」を漢字に変換 | そのまま放置 | フィラーパターンを正規表現で広めに取る |
| 長い無音でハルシネーション | モデルを変える | `--condition_on_previous_text False` を試す |
| EDLのタイムコードがズレる | 手動修正 | fps設定を確認、ソースと一致させる |
| MCP でResolveが応答しない | 何度もリトライ | Resolveが起動中＋External scripting有効を確認 |
| フィラー除去で内容も消えた | 全自動を信頼 | fillers_report.txt を人間がレビュー |

## 詳細リファレンス

- `scripts/detect_fillers.py` — 日本語フィラー検出スクリプト
- `scripts/generate_edl.py` — セグメントからEDL生成
- `scripts/optimize_srt.py` — SRT最適化
- `references/whisper_tips.md` — Whisper日本語運用Tips
- `references/resolve_mcp_commands.md` — よく使うMCPコマンド集
- `templates/project_structure.sh` — プロジェクトディレクトリ初期化スクリプト

