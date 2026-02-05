import argparse
import sys
from pathlib import Path

import mido
from mido import MetaMessage, MidiFile, MidiTrack


def remap_midi_tempo_meter(
    input_path,
    output_path,
    target_bpm=None,
    target_ts_num=None,
    target_ts_den=None,
    target_ppq=None,
):
    """
    重映射 MIDI 文件的 BPM、PPQ 和拍号，同时保持听感时长不变。
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        mid = MidiFile(input_path)
    except Exception as e:
        print(f"Error: 无法解析 MIDI: {e}")
        sys.exit(1)

    # --- 1. 预扫描：获取原始参数作为默认值 ---
    orig_bpm = 120
    orig_ts_num = 4
    orig_ts_den = 4
    orig_ppq = mid.ticks_per_beat

    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                orig_bpm = mido.tempo2bpm(msg.tempo)
            elif msg.type == "time_signature":
                orig_ts_num = msg.numerator
                orig_ts_den = msg.denominator

    # 如果用户没提供，就用原来的
    final_bpm = target_bpm if target_bpm is not None else orig_bpm
    final_ppq = target_ppq if target_ppq is not None else orig_ppq
    final_ts_num = target_ts_num if target_ts_num is not None else orig_ts_num
    final_ts_den = target_ts_den if target_ts_den is not None else orig_ts_den

    # --- 2. 提取并转换所有事件 ---
    all_events = []
    for i, track in enumerate(mid.tracks):
        abs_tick = 0
        current_tempo = mido.bpm2tempo(orig_bpm)  # 初始速度

        for msg in track:
            abs_tick += msg.time
            # 转换为绝对秒 (核心逻辑：基于原文件的 tempo map 计算)
            abs_seconds = mido.tick2second(abs_tick, mid.ticks_per_beat, current_tempo)

            if msg.type == "set_tempo":
                current_tempo = msg.tempo
                continue  # 丢弃旧速度
            if msg.type == "time_signature":
                continue  # 丢弃旧拍号

            all_events.append({"sec": abs_seconds, "msg": msg, "track": i})

    # --- 3. 构建新 MIDI ---
    new_mid = MidiFile(ticks_per_beat=final_ppq)
    new_tracks = [MidiTrack() for _ in range(len(mid.tracks))]
    for t in new_tracks:
        new_mid.tracks.append(t)

    # 写入新的全局 Meta 信息
    new_tempo_val = mido.bpm2tempo(final_bpm)
    new_tracks[0].append(MetaMessage("set_tempo", tempo=new_tempo_val, time=0))
    new_tracks[0].append(
        MetaMessage(
            "time_signature", numerator=final_ts_num, denominator=final_ts_den, time=0
        )
    )

    # --- 4. 重映射 Tick ---
    for i in range(len(mid.tracks)):
        track_events = [e for e in all_events if e["track"] == i]
        track_events.sort(key=lambda x: x["sec"])

        last_tick = 0
        for e in track_events:
            # 使用新的 tempo 和 ppq 计算新的 tick 位置
            current_abs_tick = round(
                mido.second2tick(e["sec"], final_ppq, new_tempo_val)
            )

            new_msg = e["msg"].copy()
            new_msg.time = current_abs_tick - last_tick
            new_tracks[i].append(new_msg)
            last_tick = current_abs_tick

    new_mid.save(str(output_file))
    print(f"--- 转换成功 ---")
    print(f"BPM: {orig_bpm:.2f} -> {final_bpm:.2f}")
    print(f"PPQ: {orig_ppq} -> {final_ppq}")
    print(f"拍号: {orig_ts_num}/{orig_ts_den} -> {final_ts_num}/{final_ts_den}")
    print(f"输出文件: {output_file}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="高级 MIDI 重映射工具：修改参数并保持听感时长不变"
    )
    parser.add_argument("-i", "--input", required=True, help="输入文件")
    parser.add_argument("-o", "--output", required=True, help="输出文件")
    parser.add_argument("-b", "--bpm", type=float, help="目标 BPM (可选)")
    parser.add_argument("-p", "--ppq", type=int, help="目标 PPQ (可选)")
    parser.add_argument("--ts-num", type=int, help="拍号分子 (可选)")
    parser.add_argument("--ts-den", type=int, help="拍号分母 (可选)")

    args = parser.parse_args()

    # 校验：至少得提供一个修改项
    if (
        args.bpm is None
        and args.ppq is None
        and args.ts_num is None
        and args.ts_den is None
    ):
        print(
            "错误：你没有提供任何目标参数 (-b, -p, --ts-num, --ts-den)。请至少指定一个。"
        )
        sys.exit(1)

    remap_midi_tempo_meter(
        args.input,
        args.output,
        target_bpm=args.bpm,
        target_ppq=args.ppq,
        target_ts_num=args.ts_num,
        target_ts_den=args.ts_den,
    )


if __name__ == "__main__":
    main()
