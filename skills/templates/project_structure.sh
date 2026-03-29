#!/bin/bash
# project_structure.sh — Scaffold a video project directory
#
# Usage:
#   bash project_structure.sh "MyVideoProject"
#   bash project_structure.sh "Julia-LotkaVolterra" "2026-03-28"

PROJECT_NAME="${1:-MyProject}"
DATE="${2:-$(date +%Y-%m-%d)}"
BASE_DIR="${PROJECT_NAME}_${DATE}"

echo "Creating project: ${BASE_DIR}"

mkdir -p "${BASE_DIR}"/{raw,audio,transcripts,edl,subtitles,exports}

cat > "${BASE_DIR}/README.md" << EOF
# ${PROJECT_NAME}

- Created: ${DATE}
- Status: Pre-recording

## Directory Layout

- \`raw/\`         — Source recordings (.mov, .mp4)
- \`audio/\`       — Extracted audio (.wav)
- \`transcripts/\` — Transcription results (.json, .txt)
- \`edl/\`         — Generated EDL files
- \`subtitles/\`   — Optimized SRT files
- \`exports/\`     — Final rendered output

## Workflow

1. Place source recordings in \`raw/\`
2. \`ffmpeg -i raw/input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio/audio.wav\`
3. Whisper transcription → \`transcripts/transcript.json\`
4. Filler detection → \`transcripts/clean_segments.json\`
5. EDL generation → \`edl/clean_edit.edl\`
6. Import into Resolve → edit
7. Subtitle generation → \`subtitles/subtitles.srt\`
8. Render → \`exports/\`
EOF

echo "Done: ${BASE_DIR}/"
ls -la "${BASE_DIR}/"
