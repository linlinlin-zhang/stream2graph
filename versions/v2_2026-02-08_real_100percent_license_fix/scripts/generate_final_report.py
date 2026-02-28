#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

base_dir = Path('stream2graph_dataset/final_100percent_real')

stats = {
    'total': 0,
    'valid_license': 0,
    'compilable': 0,
    'perfect': 0,
    'by_source': {}
}

invalid_licenses = {'error', 'rate_limited', 'unknown', 'other', 'timeout',
                    'not_found', 'forbidden', 'error_403', 'error_404',
                    'gitlab_unknown', 'unknown_source'}

for source in ['github', 'huggingface', 'gitlab', 'other']:
    dir_path = base_dir / source
    if not dir_path.exists():
        continue

    stats['by_source'][source] = {'total': 0, 'valid': 0, 'compilable': 0, 'perfect': 0}

    for f in dir_path.glob('*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)

            stats['total'] += 1
            stats['by_source'][source]['total'] += 1

            lic = data.get('license', 'MISSING')
            comp = data.get('compilation_status', '')

            if lic not in invalid_licenses and lic != 'MISSING':
                stats['valid_license'] += 1
                stats['by_source'][source]['valid'] += 1

            if comp == 'success':
                stats['compilable'] += 1
                stats['by_source'][source]['compilable'] += 1

            if lic not in invalid_licenses and lic != 'MISSING' and comp == 'success':
                stats['perfect'] += 1
                stats['by_source'][source]['perfect'] += 1
        except:
            pass

print('='*70)
print('STREAM2GRAPH 完美数据集 - 最终状态')
print('='*70)
print()
print(f'总样本数: {stats["total"]}')
print()
print('质量指标:')
print(f'  有效许可证: {stats["valid_license"]} ({stats["valid_license"]/stats["total"]*100:.1f}%)')
print(f'  可编译:     {stats["compilable"]} ({stats["compilable"]/stats["total"]*100:.1f}%)')
print(f'  完美样本:   {stats["perfect"]} ({stats["perfect"]/stats["total"]*100:.1f}%)')
print()
print('按来源统计:')
print('-'*70)
for source, s in stats['by_source'].items():
    valid_pct = s['valid']/s['total']*100 if s['total'] > 0 else 0
    comp_pct = s['compilable']/s['total']*100 if s['total'] > 0 else 0
    perfect_pct = s['perfect']/s['total']*100 if s['total'] > 0 else 0
    print(f'{source.upper():12} {s["total"]:4} total | {s["valid"]:4} valid ({valid_pct:5.1f}%) | {s["compilable"]:4} comp ({comp_pct:5.1f}%) | {s["perfect"]:4} perfect ({perfect_pct:5.1f}%)')

# 保存报告
report = {
    'timestamp': '2026-02-08',
    'dataset_name': 'Stream2Graph',
    'version': '2.0',
    'statistics': {
        'total': stats['total'],
        'valid_license': stats['valid_license'],
        'compilable': stats['compilable'],
        'perfect': stats['perfect'],
        'valid_license_percentage': stats['valid_license']/stats['total']*100,
        'compilable_percentage': stats['compilable']/stats['total']*100,
        'perfect_percentage': stats['perfect']/stats['total']*100
    },
    'by_source': stats['by_source']
}

with open('FINAL_DATASET_REPORT.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print()
print('='*70)
print('报告已保存: FINAL_DATASET_REPORT.json')
print('='*70)
