# Whisper 日本語運用Tips

## モデル選択

| モデル | メモリ | 日本語精度 | 速度 | 推奨環境 |
|--------|--------|-----------|------|----------|
| medium | ~5GB | 実用的 | 速い | まず試す |
| large-v3 | ~10GB | 高精度 | やや重い | 24GB Mac |
| turbo | ~6GB | 英語最適化 | 最速 | 非推奨(日本語) |

## 推奨設定

```python
result = model.transcribe(
    "audio.wav",
    language="ja",              # 必ず指定（自動検出より精度向上）
    word_timestamps=True,       # 単語レベルのタイムスタンプ
    condition_on_previous_text=False,  # ハルシネーション軽減
    verbose=False
)
```

### condition_on_previous_text=False が重要な理由

デフォルト（True）だと、前のセグメントのテキストを参考にして次を予測する。
日本語では同じフレーズの繰り返しやハルシネーションの原因になることがある。
Falseにすると各セグメントが独立して処理され、安定する。

## 音声の前処理

### ffmpeg で最適なWAVを作成

```bash
ffmpeg -i input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

- `-ar 16000` : 16kHz（Whisperの内部サンプルレート）
- `-ac 1` : モノラル（ステレオだと片チャンネルが無視される可能性）
- `-acodec pcm_s16le` : Linear PCM 16bit

### ノイズが多い場合

ffmpegの簡易ノイズ除去:
```bash
ffmpeg -i input.mov -vn -af "highpass=f=200,lowpass=f=3000,afftdn=nf=-25" -ar 16000 -ac 1 audio_clean.wav
```

## 日本語特有の注意点

### フィラーの認識パターン

Whisperが日本語フィラーをどう認識するかは不安定：
- 「えー」→ そのまま「えー」と出ることが多い
- 「あのー」→ 「あの」になることがある
- 無音区間 → 存在しない文章をハルシネーションすることがある
- 英語混じり → 「you know」「like」として認識されることがある

### 長時間音声の制限

英語以外の言語では1時間を超えるとトランスクリプションが途切れる報告あり。
対策: 30分以下のチャンクに分割してから処理する。

```bash
# 30分ずつ分割
ffmpeg -i long_audio.wav -f segment -segment_time 1800 -c copy chunk_%03d.wav
```

### 漢字変換の精度

技術用語や固有名詞は誤変換されやすい。
`initial_prompt` パラメータでヒントを与えると改善する場合がある：

```python
result = model.transcribe(
    "audio.wav",
    language="ja",
    initial_prompt="Julia言語、DifferentialEquations、ロトカ・ヴォルテラ方程式"
)
```

## Apple Silicon (M1/M2/M3) での実行

PyTorchのMPS (Metal Performance Shaders) バックエンドが自動で使われる。
ただし、一部のWhisper操作でMPSが不安定な場合がある。
その場合は環境変数で無効化：

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

## トラブルシューティング

| 症状 | 対策 |
|------|------|
| 同じ文が繰り返される | `condition_on_previous_text=False` |
| 無音区間に謎のテキスト | `condition_on_previous_text=False` + 音声前処理 |
| 処理が極端に遅い | モデルサイズを下げる / CPUフォールバックを確認 |
| 文字化けする | 出力JSONのencodingをutf-8で確認 |
| タイムスタンプがズレる | 音声のサンプルレートを16kHzに統一 |
