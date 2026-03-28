"""
generate_edl.py
clean_segments.json から CMX 3600 EDL を生成する。

Usage:
    python scripts/generate_edl.py clean_segments.json --source test --output edl/clean_edit.edl --fps 24
"""

import argparse
import json
import os
from pathlib import Path


def seconds_to_tc(seconds: float, fps: float) -> str:
    """秒をタイムコード HH:MM:SS:FF に変換する。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    f = int((seconds % 1) * fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def generate_edl(segments: list[dict], *, source: str, fps: float,
                 title: str = "FILLER_REMOVED") -> str:
    reel = Path(source).stem
    clip_name = source if "." in source else f"{source}.wav"

    lines = [
        f"TITLE: {title}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    rec_offset = 0.0
    for i, seg in enumerate(segments, 1):
        start, end = seg["start"], seg["end"]
        src_in = seconds_to_tc(start, fps)
        src_out = seconds_to_tc(end, fps)
        rec_in = seconds_to_tc(rec_offset, fps)
        rec_out = seconds_to_tc(rec_offset + (end - start), fps)

        lines.append(f"{i:03d}  {reel:<8s} AA/V  C        {src_in} {src_out} {rec_in} {rec_out}")
        lines.append(f"* FROM CLIP NAME: {clip_name}")
        rec_offset += end - start

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="clean_segments.json から EDL を生成")
    parser.add_argument("input", help="clean_segments.json のパス")
    parser.add_argument("--source", required=True, help="ソース名（リール名/クリップ名）")
    parser.add_argument("--output", default="edl/clean_edit.edl", help="出力EDLパス")
    parser.add_argument("--fps", type=float, default=24.0, help="フレームレート")
    parser.add_argument("--title", default="FILLER_REMOVED", help="EDLタイトル")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    segments = data["clean_segments"]
    edl_content = generate_edl(segments, source=args.source, fps=args.fps, title=args.title)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(edl_content)

    duration = data.get("duration", 0)
    total_clean = sum(s["end"] - s["start"] for s in segments)
    print(f"EDL生成: {args.output}")
    print(f"  区間数: {len(segments)}, FPS: {args.fps}, ソース: {args.source}")
    print(f"  元: {duration:.2f}s → 編集後: {total_clean:.2f}s")


if __name__ == "__main__":
    main()
