import json
import time
from pathlib import Path
from cscw_dialogue_engine import run_cscw_engine, Turn

def turn_to_dict(turn: Turn) -> dict:
    return {
        "turn_id": turn.turn_id,
        "role": turn.role,
        "action_type": turn.action_type,
        "utterance": turn.utterance,
        "elements_involved": turn.elements_involved,
        "is_repair": turn.is_repair
    }

def run_cscw_reverse_engineering():
    input_dir = Path('/home/lin-server/pictures/stream2graph_dataset/final_v2_9k')
    output_dir = Path('/home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = list(input_dir.glob('*.json'))
    total_files = len(files)
    print(f"--- 启动 CSCW 级逆向工程对话生成 (总数: {total_files}) ---")
    
    processed = 0
    start_time = time.time()
    
    for f in files:
        output_file = output_dir / f.name
        if output_file.exists():
            processed += 1
            continue
            
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            code = data.get('code', '')
            if not code:
                continue
                
            # 使用新一代 CSCW 引擎生成对话
            dialogue_turns = run_cscw_engine(code)
            
            # 记录数据
            data['cscw_dialogue'] = [turn_to_dict(t) for t in dialogue_turns]
            
            # 统计 Repair 发生率 (为论文统计做准备)
            repairs = sum(1 for t in dialogue_turns if t.is_repair)
            data['dialogue_metadata'] = {
                "total_turns": len(dialogue_turns),
                "repair_count": repairs,
                "grounding_acts_count": len([t for t in dialogue_turns if t.action_type in ["clarify", "confirm"]]),
                "theoretical_framework": "Grounding in Communication (Clark & Brennan, 1991)"
            }
            
            with open(output_file, 'w', encoding='utf-8') as out:
                json.dump(data, out, ensure_ascii=False, indent=2)
                
            processed += 1
            
            if processed % 500 == 0:
                elapsed = time.time() - start_time
                print(f"  进度: {processed}/{total_files} 已生成 (耗时: {elapsed:.2f}s)")
                
        except Exception as e:
            continue
            
    print(f"--- CSCW 级逆向工程生成完毕！ ---")
    print(f"成功写入目录: {output_dir}")

if __name__ == '__main__':
    run_cscw_reverse_engineering()
