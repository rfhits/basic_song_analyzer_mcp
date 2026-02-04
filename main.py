import os

import gradio as gr
import mido

# --- 验证测试 ---
SECTION_DICT = {
    "intro": "i",
    "verse": "A",
    "chorus": "B",
    "bridge": "C",
    "inst": "D",
    "pre-chorus": "P",
    "outro": "O",
    "end": "E",
}


def calculate_segmentation(bpm, beats_per_bar, msa_format):
    """calculate segmentation of a song, like i(intro) 4 A 8 B 4 A 8.

    Args:
        bpm: beats per minute.
        beats_per_bar: how many beats per measure(bar). in time signature, it is the numerator.
        msa_format: lines of "{start_time_sec} {tag}", like "0 intro\n10 verse"

    Returns:
        str: segmentation of song, like i4A8B4A8.
    """

    lines = [line.strip() for line in msa_format.strip().split("\n") if line.strip()]
    # 每秒拍数 = BPM / 60
    # 每秒小节数 = (BPM / 60) / time_sig_numerator
    bars_per_second = (bpm / 60.0) / beats_per_bar

    parsed_points = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed_points.append((float(parts[0]), parts[1].lower()))

    # 1. 计算每个时间点对应的“绝对小节位置”
    # 使用 round 确保每个节点都对齐到最接近的整小节
    milestones = []
    for timestamp, name in parsed_points:
        absolute_bar = int(round(timestamp * bars_per_second))
        milestones.append({"bar_pos": absolute_bar, "name": name})

    # 2. 计算各段原始长度 (当前位置 - 上一位置)
    raw_segments = []
    for i in range(len(milestones) - 1):
        curr_bar_pos = milestones[i]["bar_pos"]
        next_bar_pos = milestones[i + 1]["bar_pos"]
        diff_bars = next_bar_pos - curr_bar_pos

        name = milestones[i]["name"]
        raw_segments.append(
            {"label": SECTION_DICT.get(name, name[0].upper()), "bars": diff_bars}
        )

    # 2. 合并逻辑：处理 bars < 2
    # 我们使用一个 while 循环来动态处理列表，这样可以多次合并直到没有 < 2 的段落
    i = 0
    while i < len(raw_segments):
        if raw_segments[i]["bars"] < 2:
            # 情况 A: 如果是第一段，强行合入下一段 (往后合)
            if i == 0 and len(raw_segments) > 1:
                raw_segments[i + 1]["bars"] += raw_segments[i]["bars"]
                raw_segments.pop(i)
                # 不移动 i，继续检查新的第一段
                continue

            # 情况 B: 如果是最后一段或者中间段落，合入前一段 (往前合)
            elif i > 0:
                raw_segments[i - 1]["bars"] += raw_segments[i]["bars"]
                raw_segments.pop(i)
                # 删除了当前项，i 自动指向了原先的后一项，不需要移动
                continue

            # 情况 C: 只有一段且 < 2 (极端情况，直接跳过或设为2)
            else:
                raw_segments[i]["bars"] = max(2, raw_segments[i]["bars"])
                i += 1
        else:
            i += 1

    merged = raw_segments

    # 4. 递归拆分逻辑 (> 16 则拆分)
    final_result = []

    def split_recursive(label, bars):
        if bars <= 16:
            if bars > 0:
                final_result.append(f"{label}{bars}")
            return
        half = bars // 2
        remainder = bars - half
        split_recursive(label, half)
        split_recursive(label, remainder)

    for seg in merged:
        split_recursive(seg["label"], seg["bars"])

    return "".join(final_result)


def get_midi_bpm_and_meter(midi_path):
    """Get beats per minute and time signature of midi.

    Args:
        midi_path: midi file path, use absolute path.

    Returns:
        str: analysis report of the midi file.
    """
    if not os.path.exists(midi_path):
        print(f"错误: 文件 {midi_path} 不存在")
        return

    mid = mido.MidiFile(midi_path)
    events = []

    for i, track in enumerate(mid.tracks):
        total_tick = 0
        for msg in track:
            total_tick += msg.time

            # 捕获速度变化
            if msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
                events.append(
                    {"tick": total_tick, "type": "BPM", "value": round(bpm, 2)}
                )

            # 捕获拍号变化
            elif msg.type == "time_signature":
                # numerator: 分子, denominator: 分母 (MIDI 存的是 2 的幂次)
                ts = f"{msg.numerator}/{2**msg.denominator}"
                events.append(
                    {"tick": total_tick, "type": "TimeSignature", "value": ts}
                )
        print(f"Track {i}: {total_tick}")
    # 按时间线排序
    events.sort(key=lambda x: x["tick"])

    if not events:
        print("该 MIDI 文件中没有找到显式的速度或拍号元消息")
        return

    print(f"--- 分析报告: {midi_path} ---")
    ret_msg = "\n".join(
        [
            f"Tick: {e['tick']:<10} | 类型: {e['type']:<5} | 数值: {e['value']}"
            for e in events
        ]
    )

    print(ret_msg)
    return ret_msg


with gr.Blocks() as demo:
    with gr.Tab("get tempo of a midi file"):
        gr.Interface(
            fn=get_midi_bpm_and_meter,
            inputs=[gr.Textbox(label="midi path")],
            outputs=gr.Textbox(),
        )

    with gr.Tab("calculate segmentation"):
        gr.Interface(
            fn=calculate_segmentation,
            inputs=[
                gr.Number(label="BPM"),
                gr.Number(label="beats per bar"),
                gr.Textbox(label="msa structure"),
            ],
            outputs=gr.Textbox(buttons=["copy"]),
        )
if __name__ == "__main__":
    demo.launch(mcp_server=True, server_port=7869)
