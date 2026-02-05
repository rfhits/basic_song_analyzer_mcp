import os
import mido
import argparse # 导入参数解析模块

def get_midi_bpm_and_meter(midi_path):
    """获取 MIDI 的 BPM 和拍号分析报告"""
    if not os.path.exists(midi_path):
        print(f"错误: 文件 {midi_path} 不存在")
        return

    mid = mido.MidiFile(midi_path)
    events = []

    for i, track in enumerate(mid.tracks):
        total_tick = 0
        for msg in track:
            total_tick += msg.time

            if msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
                events.append(
                    {"tick": total_tick, "type": "BPM", "value": round(bpm, 2)}
                )

            elif msg.type == "time_signature":
                # 修正：mido 已经处理了 2 的幂次转换，直接使用 msg.denominator 即可
                ts = f"{msg.numerator}/{msg.denominator}"
                events.append(
                    {"tick": total_tick, "type": "TimeSignature", "value": ts}
                )
        
    # 按时间线排序
    events.sort(key=lambda x: x["tick"])

    if not events:
        print("该 MIDI 文件中没有找到显式的速度或拍号元消息")
        return

    report_header = f"--- 分析报告: {os.path.abspath(midi_path)} ---"
    report_body = "\n".join(
        [
            f"Tick: {e['tick']:<10} | 类型: {e['type']:<5} | 数值: {e['value']}"
            for e in events
        ]
    )
    
    full_report = f"{report_header}\n{report_body}"
    print(full_report)
    return full_report

# --- CLI 调用部分 ---
def main():
    """
    修改理由：
    1. 使用 argparse 提供标准 CLI 接口，支持 -i 参数。
    2. 增加了简单的错误检查。
    """
    parser = argparse.ArgumentParser(description="MIDI 速度与拍号分析工具")
    
    # 添加输入文件参数
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="待分析的 MIDI 文件路径"
    )

    args = parser.parse_args()

    # 执行分析
    get_midi_bpm_and_meter(args.input)

if __name__ == "__main__":
    main()