#!/usr/bin/env python3
"""
验证Mermaid代码的可编译性
使用Mermaid CLI (mmdc) 批量验证所有样本
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib

def validate_single_file(filepath):
    """验证单个Mermaid文件的可编译性"""
    result = {
        'file': str(filepath),
        'status': 'unknown',
        'error': None,
        'diagram_type': None,
        'code_length': 0
    }

    try:
        # 读取JSON文件
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        code = data.get('code', '')
        result['diagram_type'] = data.get('diagram_type', 'unknown')
        result['code_length'] = len(code)

        if not code or len(code) < 10:
            result['status'] = 'invalid'
            result['error'] = 'Empty or too short code'
            return result

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            # 尝试编译为SVG
            output_path = tmp_path + '.svg'

            # 使用mmdc编译
            process = subprocess.run(
                ['npx', '@mermaid-js/mermaid-cli', '-i', tmp_path, '-o', output_path, '-b', 'white'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if process.returncode == 0 and os.path.exists(output_path):
                result['status'] = 'success'
                # 计算输出文件大小
                result['output_size'] = os.path.getsize(output_path)
                # 清理输出文件
                os.remove(output_path)
            else:
                result['status'] = 'failed'
                # 提取错误信息
                error_msg = process.stderr if process.stderr else process.stdout
                # 限制错误信息长度
                if error_msg:
                    result['error'] = error_msg[:500]
                else:
                    result['error'] = 'Unknown compilation error'

        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(output_path):
                os.remove(output_path)

    except subprocess.TimeoutExpired:
        result['status'] = 'timeout'
        result['error'] = 'Compilation timeout (>30s)'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:500]

    return result

def update_file_with_validation(filepath, validation_result):
    """更新JSON文件添加验证结果"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 添加验证字段
        data['compilation_status'] = validation_result['status']
        if validation_result['error']:
            data['compilation_error'] = validation_result['error']
        if 'output_size' in validation_result:
            data['output_size'] = validation_result['output_size']

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False

def main():
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    # 收集所有JSON文件
    all_files = []
    for source_dir in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source_dir
        if dir_path.exists():
            all_files.extend(list(dir_path.glob('*.json')))

    print(f"找到 {len(all_files)} 个样本文件")
    print("开始验证可编译性...")
    print("="*60)

    # 统计
    stats = {
        'total': len(all_files),
        'success': 0,
        'failed': 0,
        'timeout': 0,
        'error': 0,
        'invalid': 0,
        'by_type': {},
        'by_source': {}
    }

    # 分批处理
    batch_size = 100
    total_batches = (len(all_files) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, len(all_files))
        batch_files = all_files[start_idx:end_idx]

        print(f"\n处理批次 {batch_idx + 1}/{total_batches} (文件 {start_idx + 1}-{end_idx})...")

        # 使用进程池并行处理
        with ProcessPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(validate_single_file, f): f for f in batch_files}

            for future in as_completed(future_to_file):
                filepath = future_to_file[future]
                try:
                    result = future.result()

                    status = result['status']
                    stats[status] = stats.get(status, 0) + 1

                    # 按类型统计
                    dtype = result.get('diagram_type', 'unknown')
                    if dtype not in stats['by_type']:
                        stats['by_type'][dtype] = {'total': 0, 'success': 0, 'failed': 0}
                    stats['by_type'][dtype]['total'] += 1
                    if status == 'success':
                        stats['by_type'][dtype]['success'] += 1
                    else:
                        stats['by_type'][dtype]['failed'] += 1

                    # 按来源统计
                    source = filepath.parts[-2]  # 父目录名
                    if source not in stats['by_source']:
                        stats['by_source'][source] = {'total': 0, 'success': 0, 'failed': 0}
                    stats['by_source'][source]['total'] += 1
                    if status == 'success':
                        stats['by_source'][source]['success'] += 1
                    else:
                        stats['by_source'][source]['failed'] += 1

                    # 更新文件
                    update_file_with_validation(filepath, result)

                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

        # 批次完成报告
        processed = min((batch_idx + 1) * batch_size, len(all_files))
        success_rate = (stats['success'] / processed * 100) if processed > 0 else 0
        print(f"  批次完成 - 已处理: {processed}/{len(all_files)}, 成功率: {success_rate:.1f}%")

    # 生成最终报告
    print("\n" + "="*60)
    print("可编译性验证完成报告")
    print("="*60)
    print(f"总计: {stats['total']}")
    print(f"成功: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"失败: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"超时: {stats['timeout']}")
    print(f"无效: {stats['invalid']}")
    print(f"错误: {stats['error']}")

    print("\n按图表类型统计:")
    for dtype, counts in sorted(stats['by_type'].items()):
        rate = (counts['success'] / counts['total'] * 100) if counts['total'] > 0 else 0
        print(f"  {dtype}: {counts['success']}/{counts['total']} ({rate:.1f}%)")

    print("\n按来源统计:")
    for source, counts in sorted(stats['by_source'].items()):
        rate = (counts['success'] / counts['total'] * 100) if counts['total'] > 0 else 0
        print(f"  {source}: {counts['success']}/{counts['total']} ({rate:.1f}%)")

    # 保存详细报告
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': stats
    }

    with open('compilability_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n详细报告已保存到 compilability_report.json")

    return stats

if __name__ == '__main__':
    main()
