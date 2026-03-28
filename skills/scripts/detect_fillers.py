"""
detect_fillers.py
Whisper の word_timestamps 付き transcript JSON からフィラーを検出し、
Silero VAD で正確なタイムスタンプに補正して、クリーン区間を JSON で出力する。

Usage:
    python detect_fillers.py transcript_filler.json --wav test.wav --duration 10.37 --output clean_segments.json
"""

import argparse
import json
import math
import struct
import wave
from dataclasses import dataclass, asdict

import torch

# --- フィラー検出パターン ---
FILLER_PATTERNS = [
    "あー", "あー、", "あ、",
    "えー", "えー、", "え、", "えっと", "えっと、",
    "うーん", "うん、", "うーん、",
    "まあ", "まあ、",
    "そのー", "そのー、", "その、",
    "なんか", "なんか、",
    "あのー", "あのー、", "あの、", "あの",
]

# Whisper は「あのー」を「あ」「の」「ー、」のように分割することがある
# → 隣接ワードを結合してからパターンマッチする
FILLER_COMBINE_PATTERNS = [
    ("あ", "の", "ー、"),
    ("あ", "のー、"),
    ("あ", "の、"),
    ("え", "ー、"),
    ("え", "っと、"),
    ("え", "っと"),
    ("そ", "の", "ー、"),
    ("う", "ー", "ん"),
    ("う", "ーん"),
    ("う", "ーん、"),
]


@dataclass
class Filler:
    text: str
    start: float
    end: float
    probability: float


@dataclass
class CleanSegment:
    start: float
    end: float


def detect_fillers(transcript_path: str) -> list[Filler]:
    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)

    fillers = []
    for segment in data["segments"]:
        words = segment.get("words", [])
        used = [False] * len(words)

        # 1) 結合パターンで検出
        for pattern in FILLER_COMBINE_PATTERNS:
            plen = len(pattern)
            for i in range(len(words) - plen + 1):
                if any(used[i + k] for k in range(plen)):
                    continue
                candidate = [words[i + k]["word"].strip() for k in range(plen)]
                if candidate == list(pattern):
                    for k in range(plen):
                        used[i + k] = True
                    combined_text = "".join(w["word"].strip() for w in words[i:i + plen])
                    avg_prob = sum(w["probability"] for w in words[i:i + plen]) / plen
                    fillers.append(Filler(
                        text=combined_text,
                        start=words[i]["start"],
                        end=words[i + plen - 1]["end"],
                        probability=avg_prob,
                    ))

        # 2) 単一ワードパターンで検出
        for i, w in enumerate(words):
            if used[i]:
                continue
            clean = w["word"].strip()
            if clean in FILLER_PATTERNS:
                used[i] = True
                fillers.append(Filler(
                    text=clean,
                    start=w["start"],
                    end=w["end"],
                    probability=w["probability"],
                ))

    fillers.sort(key=lambda f: f.start)
    return fillers


def load_wav_samples(wav_path: str) -> tuple[list[int], int]:
    """wavファイルを読み込み、サンプル列とサンプルレートを返す。"""
    w = wave.open(wav_path, "r")
    sr = w.getframerate()
    data = w.readframes(w.getnframes())
    w.close()
    samples = struct.unpack(f"<{len(data) // 2}h", data)
    return samples, sr


def run_vad(wav_path: str) -> list[dict]:
    """Silero VAD で発話区間を検出する。"""
    samples, sr = load_wav_samples(wav_path)
    wav_tensor = torch.FloatTensor(samples) / 32768.0

    model, utils = torch.hub.load(
        "snakers4/silero-vad", model="silero_vad",
        force_reload=False, trust_repo=True,
    )
    get_speech_timestamps = utils[0]
    return get_speech_timestamps(wav_tensor, model, sampling_rate=sr, return_seconds=True)


def find_energy_dropoff(samples: list[int], sr: int, start: float,
                        max_search: float = 2.0, window: float = 0.03,
                        threshold: float = 500.0) -> float:
    """startから後方にスキャンし、RMSエネルギーがthreshold以下に落ちる時点を返す。"""
    t = start
    end_limit = min(start + max_search, len(samples) / sr)
    last_above = start
    while t < end_limit:
        s = int(t * sr)
        e = int((t + window) * sr)
        if e > len(samples):
            break
        chunk = samples[s:e]
        rms = math.sqrt(sum(x * x for x in chunk) / len(chunk))
        if rms > threshold:
            last_above = t + window
        elif t > last_above + 0.05:
            # 閾値以下が50ms以上続いたらここが終了
            return round(last_above, 3)
        t += window
    return round(last_above, 3)


def correct_filler_timestamps(fillers: list[Filler], vad_segments: list[dict],
                              samples: list[int], sr: int) -> list[Filler]:
    """Whisperのフィラータイムスタンプを VAD + エネルギー解析で補正する。
    - start: VADの発話開始にスナップ
    - end: VAD開始位置からエネルギーが落ちる点を検出
    """
    corrected = []
    for f in fillers:
        whisper_mid = (f.start + f.end) / 2

        # フィラーの中心に最も近いVADセグメントを探す
        best = min(vad_segments, key=lambda v: abs((v["start"] + v["end"]) / 2 - whisper_mid))

        new_start = best["start"]
        new_end = find_energy_dropoff(samples, sr, new_start)

        corrected.append(Filler(
            text=f.text,
            start=new_start,
            end=new_end,
            probability=f.probability,
        ))

    return corrected


def build_clean_segments(fillers: list[Filler], duration: float,
                         padding: float = 0.05) -> list[CleanSegment]:
    """フィラー区間を除いたクリーンな区間リストを生成する。"""
    cuts = [(max(0, f.start - padding), min(duration, f.end + padding)) for f in fillers]

    # 重なりをマージ
    merged = []
    for s, e in sorted(cuts):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # カット区間の補集合 = キープ区間
    segments = []
    prev = 0.0
    for s, e in merged:
        if s > prev:
            segments.append(CleanSegment(start=prev, end=s))
        prev = e
    if prev < duration:
        segments.append(CleanSegment(start=prev, end=duration))

    return segments


def main():
    parser = argparse.ArgumentParser(description="Whisper transcript からフィラーを検出（VAD補正付き）")
    parser.add_argument("transcript", help="Whisper transcript JSON")
    parser.add_argument("--wav", required=True, help="元の音声ファイル（VAD補正用）")
    parser.add_argument("--duration", type=float, default=None, help="音声の長さ（秒）。省略時はwavから取得")
    parser.add_argument("--output", default="clean_segments.json", help="出力JSON")
    parser.add_argument("--padding", type=float, default=0.05, help="カット前後のパディング（秒）")
    parser.add_argument("--no-vad", action="store_true", help="VAD補正を無効化")
    args = parser.parse_args()

    # duration をwavから取得
    if args.duration is None:
        w = wave.open(args.wav, "r")
        args.duration = w.getnframes() / w.getframerate()
        w.close()

    # フィラー検出
    fillers = detect_fillers(args.transcript)
    print(f"検出フィラー数: {len(fillers)}")

    if not args.no_vad:
        # VAD 実行
        print("\nSilero VAD 実行中...")
        vad_segments = run_vad(args.wav)
        print(f"VAD発話区間数: {len(vad_segments)}")
        for v in vad_segments:
            print(f"  [{v['start']:.3f}s - {v['end']:.3f}s]")

        # 補正前後の比較
        samples, sr = load_wav_samples(args.wav)
        corrected = correct_filler_timestamps(fillers, vad_segments, samples, sr)
        print("\n=== タイムスタンプ補正 ===")
        for orig, corr in zip(fillers, corrected):
            delta_s = corr.start - orig.start
            delta_e = corr.end - orig.end
            print(f"  {orig.text}")
            print(f"    Whisper: {orig.start:.3f}s - {orig.end:.3f}s")
            print(f"    補正後:  {corr.start:.3f}s - {corr.end:.3f}s  (Δstart={delta_s:+.3f}s, Δend={delta_e:+.3f}s)")
        fillers = corrected
    else:
        for f in fillers:
            print(f"  [{f.start:.2f}s - {f.end:.2f}s] \"{f.text}\"")

    # クリーン区間生成
    clean = build_clean_segments(fillers, args.duration, args.padding)

    result = {
        "duration": args.duration,
        "fillers": [asdict(f) for f in fillers],
        "clean_segments": [asdict(s) for s in clean],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_clean = sum(s.end - s.start for s in clean)
    print(f"\n元: {args.duration:.2f}s → 編集後: {total_clean:.2f}s (カット: {args.duration - total_clean:.2f}s)")
    print(f"出力: {args.output}")


if __name__ == "__main__":
    main()
