#!/usr/bin/env python3
"""
过滤高质量数据集子集
条件：有效许可证 + 可编译
"""
import json
import shutil
from pathlib import Path
from collections import Counter

def filter_quality_dataset():
    base_dir = Path('stream2graph_dataset/final_100percent_real')
    output_dir = Path('stream2graph_dataset/high_quality_subset')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 无效许可证列表
    invalid_licenses = {
        'error', 'rate_limited', 'unknown', 'other', 'timeout',
        'not_found', 'forbidden', 'error_403', 'error_404',
        'gitlab_unknown', 'unknown_source'
    }

    stats = {
        'total': 0,
        'valid_license': 0,
        'compilable': 0,
        'high_quality': 0,  # 有效许可证 + 可编译
        'by_source': Counter(),
        'by_type': Counter(),
        'by_license': Counter()
    }

    # 为每个来源创建目录
    for source in ['github', 'huggingface', 'gitlab', 'other']:
        (output_dir / source).mkdir(exist_ok=True)

    for source in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source
        if not dir_path.exists():
            continue

        for json_file in dir_path.glob('*.json'):
            stats['total'] += 1

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                license_key = data.get('license', '')
                compilation_status = data.get('compilation_status', '')
                diagram_type = data.get('diagram_type', 'unknown')

                # 检查有效许可证
                has_valid_license = license_key not in invalid_licenses

                # 检查可编译性
                is_compilable = compilation_status == 'success'

                if has_valid_license:
                    stats['valid_license'] += 1

                if is_compilable:
                    stats['compilable'] += 1

                # 高质量标准：有效许可证 + 可编译
                if has_valid_license and is_compilable:
                    stats['high_quality'] += 1
                    stats['by_source'][source] += 1
                    stats['by_type'][diagram_type] += 1
                    stats['by_license'][license_key] += 1

                    # 复制到高质量子集目录
                    output_file = output_dir / source / json_file.name
                    shutil.copy2(json_file, output_file)

            except Exception as e:
                print(f"Error processing {json_file}: {e}")

    # 生成报告
    print("="*60)
    print("High Quality Dataset Filter Report")
    print("="*60)
    print(f"\nTotal samples: {stats['total']}")
    print(f"Valid license: {stats['valid_license']} ({stats['valid_license']/stats['total']*100:.1f}%)")
    print(f"Compilable: {stats['compilable']} ({stats['compilable']/stats['total']*100:.1f}%)")
    print(f"High quality (both): {stats['high_quality']} ({stats['high_quality']/stats['total']*100:.1f}%)")

    print("\nBy Source:")
    for source, count in stats['by_source'].most_common():
        print(f"  {source}: {count}")

    print("\nBy Diagram Type:")
    for dtype, count in stats['by_type'].most_common():
        print(f"  {dtype}: {count}")

    print("\nBy License:")
    for license, count in stats['by_license'].most_common():
        print(f"  {license}: {count}")

    # 保存报告
    report = {
        'timestamp': '2026-02-08',
        'statistics': {
            'total': stats['total'],
            'valid_license': stats['valid_license'],
            'compilable': stats['compilable'],
            'high_quality': stats['high_quality'],
            'valid_license_percentage': stats['valid_license']/stats['total']*100,
            'compilable_percentage': stats['compilable']/stats['total']*100,
            'high_quality_percentage': stats['high_quality']/stats['total']*100,
        },
        'by_source': dict(stats['by_source']),
        'by_type': dict(stats['by_type']),
        'by_license': dict(stats['by_license'])
    }

    with open('high_quality_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print(f"High quality dataset saved to: {output_dir}")
    print("Report saved to: high_quality_report.json")
    print("="*60)

    return stats

if __name__ == '__main__':
    filter_quality_dataset()
