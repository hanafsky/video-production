#!/bin/bash
# project_structure.sh — 動画プロジェクトのディレクトリ構造を初期化
#
# Usage:
#   bash project_structure.sh "MyVideoProject"
#   bash project_structure.sh "Julia-LotkaVolterra" "2026-03-28"

PROJECT_NAME="${1:-MyProject}"
DATE="${2:-$(date +%Y-%m-%d)}"
BASE_DIR="${PROJECT_NAME}_${DATE}"

echo "📁 プロジェクト作成: ${BASE_DIR}"

mkdir -p "${BASE_DIR}"/{raw,audio,transcripts,edl,subtitles,exports}

cat > "${BASE_DIR}/README.md" << EOF
# ${PROJECT_NAME}

- 作成日: ${DATE}
- ステータス: 収録前

## ディレクトリ構成

- \`raw/\` — 収録素材 (.mov, .mp4)
- \`audio/\` — 抽出した音声 (.wav)
- \`transcripts/\` — 文字起こし結果 (.json, .txt)
- \`edl/\` — 生成した EDL
- \`subtitles/\` — 最適化済み SRT
- \`exports/\` — 最終出力

## ワークフロー

1. \`raw/\` に収録素材を配置
2. \`ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav\`
3. Whisper で文字起こし → \`transcripts/transcript.json\`
4. フィラー検出 → \`transcripts/clean_segments.json\`
5. EDL 生成 → \`edl/clean_edit.edl\`
6. Resolve にインポート → 編集
7. 字幕生成 → \`subtitles/subtitles.srt\`
8. レンダリング → \`exports/\`
EOF

echo "✅ 完了: ${BASE_DIR}/"
ls -la "${BASE_DIR}/"
