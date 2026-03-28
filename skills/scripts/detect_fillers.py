#!/usr/bin/env python3
"""
detect_fillers.py — 日本語フィラーワード検出・除去スクリプト

Whisperの出力JSONからフィラーワードを含むセグメントを検出し、
クリーンなセグメントリストを生成する。

Usage:
    python detect_fillers.py transcript.json --output clean_segments.json
    python detect_fillers.py transcript.json --output clean_segments.json --threshold 0.7
    python detect_fillers.py transcript.json --report-only
"""

import json
import re
import argparse
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


# ── 日本語フィラーパターン定義 ──────────────────────────────────

# 完全一致でフィラーと判定するワード
FILLER_EXACT = {
    # 典型的なフィラー
    "えー", "えーと", "えーっと", "えっと",
    "あー", "あのー", "あの",
    "うーん", "うん", "うーんと",
    "まあ", "まぁ",
    "そのー", "その",
    "なんか", "なんだろう",
    "ちょっと",
    # 英語フィラー（日本語話者が混ぜることがある）
    "um", "uh", "uhm", "ah", "er", "hmm",
    # Whisperが日本語フィラーを英語として認識するケース
    "you know", "like", "so",
}

# 正規表現でフィラーと判定するパターン
FILLER_PATTERNS = [
    r"^えー+$",           # 「えーー」等の伸ばし
    r"^あー+$",           # 「あーー」等
    r"^うー+ん?$",        # 「うーーん」等
    r"^ま[あぁー]+$",     # 「まぁー」等
    r"^そ[のー]+$",       # 「そのー」等
    r"^え[ーっ]*と$",     # 「えーっと」等
    r"^あの[ーう]*$",     # 「あのー」等
    r"^\.\.\.$",          # Whisperが無音を「...」として出力することがある
    r"^\.+$",             # ドットのみ
]

# セグメント内のフィラー部分を検出する（部分一致）
FILLER_INLINE_PATTERNS = [
    r"えー+と?",
    r"あー+",
    r"あのー?",
    r"うー+ん",
    r"まぁ?",
    r"そのー",
    r"なんか",
]


@dataclass
class Segment:
    """文字起こしセグメント"""
    id: int
    start: float
    end: float
    text: str
    is_filler: bool = False
    filler_ratio: float = 0.0
    filler_words: Optional[list] = None


def load_transcript(path: str) -> dict:
    """Whisper出力JSONを読み込む"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_filler_text(text: str) -> tuple[bool, float, list]:
    """
    テキストがフィラーかどうか判定する。
    
    Returns:
        (is_filler, filler_ratio, detected_fillers)
        - is_filler: フィラーのみで構成されているか
        - filler_ratio: テキスト中のフィラー文字の割合 (0.0〜1.0)
        - detected_fillers: 検出されたフィラーワードのリスト
    """
    cleaned = text.strip()
    if not cleaned:
        return True, 1.0, ["(empty)"]

    detected = []

    # 完全一致チェック
    if cleaned in FILLER_EXACT:
        return True, 1.0, [cleaned]

    # 正規表現パターンチェック（完全一致）
    for pattern in FILLER_PATTERNS:
        if re.match(pattern, cleaned):
            return True, 1.0, [cleaned]

    # 部分一致でフィラー比率を計算
    total_len = len(cleaned)
    filler_chars = 0

    for pattern in FILLER_INLINE_PATTERNS:
        for match in re.finditer(pattern, cleaned):
            filler_chars += len(match.group())
            detected.append(match.group())

    ratio = filler_chars / total_len if total_len > 0 else 0.0

    return ratio > 0.8, ratio, detected


def detect_silence(segments: list[Segment], min_gap: float = 1.0) -> list[dict]:
    """セグメント間の無音区間を検出する"""
    silences = []
    for i in range(len(segments) - 1):
        gap = segments[i + 1].start - segments[i].end
        if gap >= min_gap:
            silences.append({
                "start": segments[i].end,
                "end": segments[i + 1].start,
                "duration": gap
            })
    return silences


def analyze_transcript(transcript: dict, threshold: float = 0.7) -> tuple[list[Segment], list[Segment]]:
    """
    トランスクリプトを解析し、クリーン/フィラーに分類する。
    
    Args:
        transcript: Whisper出力JSON
        threshold: フィラー判定の閾値 (0.0〜1.0)
    
    Returns:
        (clean_segments, filler_segments)
    """
    clean = []
    fillers = []

    for i, seg in enumerate(transcript.get("segments", [])):
        text = seg.get("text", "").strip()
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)

        is_filler, ratio, detected = is_filler_text(text)

        segment = Segment(
            id=i,
            start=start,
            end=end,
            text=text,
            is_filler=is_filler or ratio >= threshold,
            filler_ratio=ratio,
            filler_words=detected if detected else None
        )

        if segment.is_filler:
            fillers.append(segment)
        else:
            clean.append(segment)

    return clean, fillers


def merge_close_segments(segments: list[Segment], max_gap: float = 0.3) -> list[Segment]:
    """
    近接するクリーンセグメントを結合する。
    カット間のギャップが max_gap 秒以下なら結合。
    """
    if not segments:
        return []

    merged = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg.start - prev.end <= max_gap:
            # 結合
            merged[-1] = Segment(
                id=prev.id,
                start=prev.start,
                end=seg.end,
                text=prev.text + " " + seg.text,
                is_filler=False,
                filler_ratio=0.0
            )
        else:
            merged.append(seg)

    return merged


def add_handles(segments: list[Segment], handle: float = 0.1) -> list[Segment]:
    """各セグメントの前後にハンドル（余白）を追加"""
    handled = []
    for seg in segments:
        handled.append(Segment(
            id=seg.id,
            start=max(0.0, seg.start - handle),
            end=seg.end + handle,
            text=seg.text,
            is_filler=seg.is_filler,
            filler_ratio=seg.filler_ratio
        ))
    return handled


def generate_report(
    clean: list[Segment],
    fillers: list[Segment],
    silences: list[dict],
    total_duration: float
) -> str:
    """フィラーレポートを生成"""
    lines = []
    lines.append("=" * 60)
    lines.append("フィラー検出レポート")
    lines.append("=" * 60)
    lines.append("")

    # サマリー
    total_segments = len(clean) + len(fillers)
    filler_duration = sum(f.end - f.start for f in fillers)
    clean_duration = sum(c.end - c.start for c in clean)
    silence_duration = sum(s["duration"] for s in silences)

    lines.append(f"総セグメント数:    {total_segments}")
    lines.append(f"クリーン:          {len(clean)} セグメント ({clean_duration:.1f}秒)")
    lines.append(f"フィラー:          {len(fillers)} セグメント ({filler_duration:.1f}秒)")
    lines.append(f"無音区間:          {len(silences)} 箇所 ({silence_duration:.1f}秒)")
    lines.append(f"総音声長:          {total_duration:.1f}秒")
    lines.append(f"削減見込み:        {filler_duration + silence_duration:.1f}秒 "
                 f"({(filler_duration + silence_duration) / total_duration * 100:.1f}%)")
    lines.append("")

    # フィラー詳細
    lines.append("-" * 60)
    lines.append("検出されたフィラー一覧")
    lines.append("-" * 60)
    for f in fillers:
        tc_start = f"{int(f.start // 60):02d}:{f.start % 60:05.2f}"
        tc_end = f"{int(f.end // 60):02d}:{f.end % 60:05.2f}"
        lines.append(f"  [{tc_start} - {tc_end}] \"{f.text}\" (ratio: {f.filler_ratio:.2f})")

    lines.append("")
    lines.append("⚠️  上記リストを確認し、誤検出がないかレビューしてください。")
    lines.append("    内容のある発話が含まれている場合は、手動で復元してください。")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="日本語フィラーワード検出・除去")
    parser.add_argument("input", help="Whisper出力のJSONファイルパス")
    parser.add_argument("--output", "-o", help="クリーンセグメントの出力先 (JSON)")
    parser.add_argument("--report", "-r", help="フィラーレポートの出力先 (TXT)")
    parser.add_argument("--threshold", "-t", type=float, default=0.7,
                        help="フィラー判定閾値 (0.0-1.0, default: 0.7)")
    parser.add_argument("--handle", type=float, default=0.1,
                        help="セグメント前後のハンドル秒数 (default: 0.1)")
    parser.add_argument("--merge-gap", type=float, default=0.3,
                        help="セグメント結合の最大ギャップ秒数 (default: 0.3)")
    parser.add_argument("--report-only", action="store_true",
                        help="レポートのみ出力（セグメント出力しない）")
    args = parser.parse_args()

    # 読み込み
    transcript = load_transcript(args.input)

    # 解析
    clean, fillers = analyze_transcript(transcript, threshold=args.threshold)
    all_segments = sorted(clean + fillers, key=lambda s: s.start)
    silences = detect_silence(all_segments)

    # 総再生時間
    total_duration = max((s.end for s in all_segments), default=0.0)

    # レポート生成
    report = generate_report(clean, fillers, silences, total_duration)
    print(report)

    report_path = args.report or args.input.replace(".json", "_fillers_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nレポート保存: {report_path}")

    if args.report_only:
        return

    # クリーンセグメントの後処理
    clean_merged = merge_close_segments(clean, max_gap=args.merge_gap)
    clean_final = add_handles(clean_merged, handle=args.handle)

    # 出力
    output_path = args.output or args.input.replace(".json", "_clean.json")
    output_data = {
        "source": args.input,
        "threshold": args.threshold,
        "total_duration": total_duration,
        "clean_count": len(clean_final),
        "filler_count": len(fillers),
        "segments": [asdict(s) for s in clean_final]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"クリーンセグメント保存: {output_path} ({len(clean_final)} segments)")


if __name__ == "__main__":
    main()
