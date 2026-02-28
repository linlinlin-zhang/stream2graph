import json
import time
from pathlib import Path
from dialogue_reverse_engineering import DialogueGenerator, ConversationAnalyzer

def run_reverse_engineering():
    input_dir = Path('/home/lin-server/pictures/stream2graph_dataset/final_v2_9k')
    output_dir = Path('/home/lin-server/pictures/stream2graph_dataset/dialogue_dataset')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = DialogueGenerator()
    analyzer = ConversationAnalyzer()
    
    files = list(input_dir.glob('*.json'))
    total_files = len(files)
    print(f"--- 启动大规模逆向工程对话生成 (总数: {total_files}) ---")
    
    processed = 0
    failed = 0
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
                failed += 1
                continue
                
            # 生成对话
            dialogue = generator.generate_dialogue(code)
            dialogue_json = generator.dialogue_to_json(dialogue)
            stats = analyzer.analyze(dialogue)
            
            # 将对话和统计信息添加到原始数据中
            data['dialogue'] = dialogue_json
            data['dialogue_stats'] = stats
            
            with open(output_file, 'w', encoding='utf-8') as out:
                json.dump(data, out, ensure_ascii=False, indent=2)
                
            processed += 1
            
            if processed % 500 == 0:
                elapsed = time.time() - start_time
                print(f"  进度: {processed}/{total_files} 已生成 (耗时: {elapsed:.2f}s)")
                
        except Exception as e:
            failed += 1
            # print(f"Error processing {f.name}: {e}")
            continue
            
    print(f"--- 逆向工程生成完毕！ ---")
    print(f"成功: {processed}, 失败: {failed}")

if __name__ == '__main__':
    run_reverse_engineering()
