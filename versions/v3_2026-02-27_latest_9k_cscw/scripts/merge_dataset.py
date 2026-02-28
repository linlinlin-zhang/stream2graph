import os
import shutil
from pathlib import Path

def merge_datasets():
    base_dir = Path('/home/lin-server/pictures/stream2graph_dataset')
    source_dirs = [
        base_dir / 'v3_verified_final',
        base_dir / 'v4_industrial_source',
        base_dir / 'v5_augmented'
    ]
    output_dir = base_dir / 'final_v2_9k'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_copied = 0
    for d in source_dirs:
        if not d.exists():
            continue
        print(f"合并目录: {d.name}")
        for f in d.glob('*.json'):
            target_path = output_dir / f.name
            if not target_path.exists():
                shutil.copy(f, target_path)
                total_copied += 1
                
    print(f"数据合拢完成，统一存放在 final_v2_9k 目录！")
    print(f"本次复制文件总数: {total_copied}")
    
    # 验证最终数量
    final_count = len(list(output_dir.glob('*.json')))
    print(f"final_v2_9k 目录实际文件总数: {final_count}")

if __name__ == '__main__':
    merge_datasets()
