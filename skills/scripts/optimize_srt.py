#!/usr/bin/env python3
"""
optimize_srt.py — Whisper出力のSRTを日本語動画向けに最適化

Whisperの生出力SRTを校正・整形し、YouTube/動画用に最適化する。

処理内容:
- フィラーワードの除去
- 1行あたりの文字数制限（改行挿入）
- 短すぎる字幕の結合
- 空字幕の削除
- タイムスタンプの再採番

Usage:
    python optimize_srt.py transcript.json --output subtitles.srt
    python optimize_srt.py transcript.json --max-chars 20 --min-duration 1.0
    python optimize_srt.py input.srt --output optimized.srt
"""

import json
import re
import argparse
from pathlib import Path
from dataclasses import dataclass


# フィラーワード（除去対象）
FILLER_WORDS = {
    "えー", "えーと", "えーっと", "えっと",
    "あー", "あのー", "あの",
    "うーん", "うーんと",
    "まあ", "まぁ",
    "そのー",
    "なんか",
}

FILLER_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(w) for w in FILLER_WORDS) + r")[、。]?\s*"
)


@dataclass
class Subtitle:
    index: int
    start: float
    end: float
    text: str


def seconds_to_srt_time(seconds: float) -> str:
    """秒数をSRT形式のタイムスタンプに変換 (HH:MM:SS,mmm)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_time(time_str: str) -> float:
    """SRT形式のタイムスタンプを秒数に変換"""
    time_str = time_str.strip()
    h, m, rest = time_str.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def load_from_whisper_json(path: str) -> list[Subtitle]:
    """Whisper出力JSONからSubtitleリストを作成"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    subs = []
    for i, seg in enumerate(data.get("segments", [])):
        subs.append(Subtitle(
            index=i + 1,
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip()
        ))
    return subs


def load_from_srt(path: str) -> list[Subtitle]:
    """SRTファイルからSubtitleリストを作成"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    subs = []
    blocks = re.split(r"\n\n+", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        index = int(lines[0])
        times = lines[1].split(" --> ")
        start = parse_srt_time(times[0])
        end = parse_srt_time(times[1])
        text = "\n".join(lines[2:])

        subs.append(Subtitle(index=index, start=start, end=end, text=text))

    return subs


def remove_fillers(text: str) -> str:
    """テキストからフィラーワードを除去"""
    cleaned = FILLER_PATTERN.sub("", text)
    # 連続する空白を整理
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def wrap_text(text: str, max_chars: int = 20) -> str:
    """テキストを指定文字数で改行"""
    if len(text) <= max_chars:
        return text

    # 句読点での改行を優先
    break_points = [m.end() for m in re.finditer(r"[、。！？]", text)]

    if break_points:
        # 句読点のうち、max_charsに最も近い位置で改行
        best = min(break_points, key=lambda p: abs(p - max_chars))
        if best < len(text):
            return text[:best] + "\n" + wrap_text(text[best:], max_chars)

    # 句読点がない場合、max_chars位置で強制改行
    return text[:max_chars] + "\n" + wrap_text(text[max_chars:], max_chars)


def optimize_subtitles(
    subs: list[Subtitle],
    max_chars: int = 20,
    min_duration: float = 1.0,
    remove_filler: bool = True
) -> list[Subtitle]:
    """字幕リストを最適化"""

    optimized = []

    for sub in subs:
        text = sub.text

        # フィラー除去
        if remove_filler:
            text = remove_fillers(text)

        # 空になったら除外
        if not text:
            continue

        # テキスト改行
        text = wrap_text(text, max_chars)

        optimized.append(Subtitle(
            index=0,  # 後で再採番
            start=sub.start,
            end=sub.end,
            text=text
        ))

    # 短い字幕の結合
    merged = []
    for sub in optimized:
        if merged and (sub.start - merged[-1].end < 0.1) and (sub.end - merged[-1].start < min_duration * 2):
            # 前の字幕と結合
            prev = merged[-1]
            combined_text = prev.text.replace("\n", " ") + " " + sub.text.replace("\n", " ")
            merged[-1] = Subtitle(
                index=0,
                start=prev.start,
                end=sub.end,
                text=wrap_text(combined_text.strip(), max_chars)
            )
        else:
            merged.append(sub)

    # 再採番
    for i, sub in enumerate(merged):
        sub.index = i + 1

    return merged


def export_srt(subs: list[Subtitle]) -> str:
    """SubtitleリストをSRT形式の文字列に変換"""
    blocks = []
    for sub in subs:
        start_tc = seconds_to_srt_time(sub.start)
        end_tc = seconds_to_srt_time(sub.end)
        blocks.append(f"{sub.index}\n{start_tc} --> {end_tc}\n{sub.text}")
    return "\n\n".join(blocks) + "\n"


def main():
    parser = argparse.ArgumentParser(description="SRT最適化（日本語動画向け）")
    parser.add_argument("input", help="入力ファイル (.json or .srt)")
    parser.add_argument("--output", "-o", help="出力SRTファイルパス")
    parser.add_argument("--max-chars", type=int, default=20,
                        help="1行の最大文字数 (default: 20)")
    parser.add_argument("--min-duration", type=float, default=1.0,
                        help="字幕の最小表示秒数 (default: 1.0)")
    parser.add_argument("--keep-fillers", action="store_true",
                        help="フィラーワードを残す")
    args = parser.parse_args()

    input_path = Path(args.input)

    # 入力形式の判定
    if input_path.suffix == ".json":
        subs = load_from_whisper_json(args.input)
    elif input_path.suffix == ".srt":
        subs = load_from_srt(args.input)
    else:
        print(f"エラー: 非対応の入力形式: {input_path.suffix}", file=__import__("sys").stderr)
        return

    print(f"入力: {len(subs)} 字幕エントリ")

    # 最適化
    optimized = optimize_subtitles(
        subs,
        max_chars=args.max_chars,
        min_duration=args.min_duration,
        remove_filler=not args.keep_fillers
    )

    print(f"最適化後: {len(optimized)} 字幕エントリ")

    # 出力
    output_path = args.output or str(input_path.with_suffix(".srt"))
    srt_content = export_srt(optimized)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"SRT保存: {output_path}")

    # 統計
    total_chars = sum(len(s.text.replace("\n", "")) for s in optimized)
    total_duration = max((s.end for s in optimized), default=0) - min((s.start for s in optimized), default=0)
    print(f"総文字数: {total_chars}")
    print(f"総尺: {total_duration:.1f}秒")


if __name__ == "__main__":
    main()
