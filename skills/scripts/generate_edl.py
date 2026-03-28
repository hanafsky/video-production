#!/usr/bin/env python3
"""
generate_edl.py — クリーンセグメントから CMX 3600 EDL を生成

detect_fillers.py の出力 (clean_segments.json) から
DaVinci Resolve にインポート可能な EDL ファイルを生成する。

Usage:
    python generate_edl.py clean_segments.json --fps 24 --output clean_edit.edl
    python generate_edl.py clean_segments.json --fps 23.976 --title "MyProject"
"""

import json
import argparse
import math
from pathlib import Path


def seconds_to_timecode(seconds: float, fps: float) -> str:
    """秒数をSMPTEタイムコード (HH:MM:SS:FF) に変換"""
    total_frames = int(round(seconds * fps))
    ff = total_frames % int(fps)
    total_seconds = total_frames // int(fps)
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def generate_edl(
    segments: list[dict],
    fps: float = 24.0,
    title: str = "CleanEdit",
    source_name: str = "source"
) -> str:
    """
    セグメントリストから CMX 3600 EDL を生成。
    
    Args:
        segments: clean_segments.json の "segments" リスト
        fps: フレームレート
        title: EDLタイトル
        source_name: ソースクリップ名（リールネーム）
    
    Returns:
        EDL文字列
    """
    lines = []
    lines.append(f"TITLE: {title}")
    lines.append(f"FCM: NON-DROP FRAME")
    lines.append("")

    # レコードタイムコードは 01:00:00:00 開始（業界標準）
    record_offset = 3600.0  # 1時間

    current_record = record_offset

    for i, seg in enumerate(segments):
        edit_num = i + 1
        src_start = seg["start"]
        src_end = seg["end"]
        duration = src_end - src_start

        src_in = seconds_to_timecode(src_start, fps)
        src_out = seconds_to_timecode(src_end, fps)
        rec_in = seconds_to_timecode(current_record, fps)
        rec_out = seconds_to_timecode(current_record + duration, fps)

        # 8文字のリールネーム（CMX 3600仕様）
        reel = source_name[:8].ljust(8)

        # EDLイベント行: EDIT# REEL TRACK TRANS SRC_IN SRC_OUT REC_IN REC_OUT
        lines.append(f"{edit_num:03d}  {reel} V     C        {src_in} {src_out} {rec_in} {rec_out}")

        current_record += duration

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="クリーンセグメントからEDLを生成")
    parser.add_argument("input", help="clean_segments.json のパス")
    parser.add_argument("--fps", type=float, default=24.0,
                        help="フレームレート (default: 24.0)")
    parser.add_argument("--title", default="CleanEdit",
                        help="EDLタイトル (default: CleanEdit)")
    parser.add_argument("--source", default="source",
                        help="ソースクリップ名/リールネーム")
    parser.add_argument("--output", "-o", help="出力EDLファイルパス")
    args = parser.parse_args()

    # 読み込み
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        print("エラー: セグメントが空です", file=__import__("sys").stderr)
        return

    # EDL生成
    edl_content = generate_edl(
        segments=segments,
        fps=args.fps,
        title=args.title,
        source_name=args.source
    )

    # 出力
    output_path = args.output or args.input.replace("_clean.json", ".edl").replace(".json", ".edl")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(edl_content)

    total_duration = sum(s["end"] - s["start"] for s in segments)
    print(f"EDL生成完了: {output_path}")
    print(f"  イベント数: {len(segments)}")
    print(f"  総尺: {total_duration:.1f}秒")
    print(f"  FPS: {args.fps}")


if __name__ == "__main__":
    main()
