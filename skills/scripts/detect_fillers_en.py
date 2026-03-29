"""
detect_fillers_en.py
Detect English filler words from a Whisper transcript JSON (with word_timestamps),
correct timestamps using Silero VAD, and output clean segments as JSON.

Usage:
    python detect_fillers_en.py transcript.json --wav audio.wav --output clean_segments.json
"""

import argparse
import json
import math
import struct
import wave
from dataclasses import dataclass, asdict

import torch

# --- English filler patterns ---
FILLER_PATTERNS = [
    "um", "um,", "umm", "umm,",
    "uh", "uh,", "uhh", "uhh,",
    "ah", "ah,", "ahh", "ahh,",
    "er", "er,", "err", "err,",
    "hmm", "hmm,", "hm", "hm,",
    "like,", "like",
    "so,", "so",
    "right,", "right",
    "okay,", "okay",
    "well,", "well",
    "basically,", "basically",
    "actually,", "actually",
]

# Multi-word filler combinations that Whisper may split across words
FILLER_COMBINE_PATTERNS = [
    ("you", "know"),
    ("you", "know,"),
    ("I", "mean"),
    ("I", "mean,"),
    ("sort", "of"),
    ("sort", "of,"),
    ("kind", "of"),
    ("kind", "of,"),
    ("or", "something"),
    ("or", "something,"),
    ("and", "stuff"),
    ("and", "stuff,"),
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

        # 1) Multi-word filler detection
        for pattern in FILLER_COMBINE_PATTERNS:
            plen = len(pattern)
            for i in range(len(words) - plen + 1):
                if any(used[i + k] for k in range(plen)):
                    continue
                candidate = [words[i + k]["word"].strip().lower() for k in range(plen)]
                target = [p.lower() for p in pattern]
                if candidate == target:
                    for k in range(plen):
                        used[i + k] = True
                    combined_text = " ".join(w["word"].strip() for w in words[i:i + plen])
                    avg_prob = sum(w["probability"] for w in words[i:i + plen]) / plen
                    fillers.append(Filler(
                        text=combined_text,
                        start=words[i]["start"],
                        end=words[i + plen - 1]["end"],
                        probability=avg_prob,
                    ))

        # 2) Single-word filler detection
        for i, w in enumerate(words):
            if used[i]:
                continue
            clean = w["word"].strip().lower().rstrip(",")
            # Check against patterns (case-insensitive, ignore trailing comma)
            if clean in {p.lower().rstrip(",") for p in FILLER_PATTERNS}:
                used[i] = True
                fillers.append(Filler(
                    text=w["word"].strip(),
                    start=w["start"],
                    end=w["end"],
                    probability=w["probability"],
                ))

    fillers.sort(key=lambda f: f.start)
    return fillers


def load_wav_samples(wav_path: str) -> tuple[list[int], int]:
    """Load a WAV file and return (samples, sample_rate)."""
    w = wave.open(wav_path, "r")
    sr = w.getframerate()
    data = w.readframes(w.getnframes())
    w.close()
    samples = struct.unpack(f"<{len(data) // 2}h", data)
    return samples, sr


def run_vad(wav_path: str) -> list[dict]:
    """Run Silero VAD to detect speech segments."""
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
    """Scan forward from start and return the point where RMS energy drops below threshold."""
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
            return round(last_above, 3)
        t += window
    return round(last_above, 3)


def correct_filler_timestamps(fillers: list[Filler], vad_segments: list[dict],
                              samples: list[int], sr: int) -> list[Filler]:
    """Correct Whisper filler timestamps using VAD + energy analysis.
    - start: snap to nearest VAD speech onset
    - end: find energy dropoff from VAD start
    """
    corrected = []
    for f in fillers:
        whisper_mid = (f.start + f.end) / 2
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
    """Build a list of clean (non-filler) segments."""
    cuts = [(max(0, f.start - padding), min(duration, f.end + padding)) for f in fillers]

    # Merge overlapping cuts
    merged = []
    for s, e in sorted(cuts):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Complement of cuts = segments to keep
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
    parser = argparse.ArgumentParser(description="Detect English fillers from Whisper transcript (with VAD correction)")
    parser.add_argument("transcript", help="Whisper transcript JSON")
    parser.add_argument("--wav", required=True, help="Source audio file (for VAD correction)")
    parser.add_argument("--duration", type=float, default=None, help="Audio duration in seconds (auto-detected from WAV if omitted)")
    parser.add_argument("--output", default="clean_segments.json", help="Output JSON path")
    parser.add_argument("--padding", type=float, default=0.05, help="Padding around cuts in seconds")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD correction")
    args = parser.parse_args()

    # Get duration from WAV if not specified
    if args.duration is None:
        w = wave.open(args.wav, "r")
        args.duration = w.getnframes() / w.getframerate()
        w.close()

    # Detect fillers
    fillers = detect_fillers(args.transcript)
    print(f"Fillers detected: {len(fillers)}")

    if not args.no_vad:
        print("\nRunning Silero VAD...")
        vad_segments = run_vad(args.wav)
        print(f"VAD speech segments: {len(vad_segments)}")
        for v in vad_segments:
            print(f"  [{v['start']:.3f}s - {v['end']:.3f}s]")

        samples, sr = load_wav_samples(args.wav)
        corrected = correct_filler_timestamps(fillers, vad_segments, samples, sr)
        print("\n=== Timestamp Correction ===")
        for orig, corr in zip(fillers, corrected):
            delta_s = corr.start - orig.start
            delta_e = corr.end - orig.end
            print(f"  {orig.text}")
            print(f"    Whisper:    {orig.start:.3f}s - {orig.end:.3f}s")
            print(f"    Corrected:  {corr.start:.3f}s - {corr.end:.3f}s  (Δstart={delta_s:+.3f}s, Δend={delta_e:+.3f}s)")
        fillers = corrected
    else:
        for f in fillers:
            print(f"  [{f.start:.2f}s - {f.end:.2f}s] \"{f.text}\"")

    # Build clean segments
    clean = build_clean_segments(fillers, args.duration, args.padding)

    result = {
        "duration": args.duration,
        "fillers": [asdict(f) for f in fillers],
        "clean_segments": [asdict(s) for s in clean],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_clean = sum(s.end - s.start for s in clean)
    print(f"\nOriginal: {args.duration:.2f}s -> Edited: {total_clean:.2f}s (cut: {args.duration - total_clean:.2f}s)")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
