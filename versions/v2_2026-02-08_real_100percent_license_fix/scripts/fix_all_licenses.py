#!/usr/bin/env python3
"""
修复所有数据集的许可证信息
使用GitHub API Token批量获取正确的许可证
"""
import json
import os
import re
import time
import requests
from pathlib import Path
from datetime import datetime
from collections import Counter

# GitHub API Token
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'

def get_github_license(repo_url, token):
    """从GitHub API获取仓库许可证信息"""
    match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
    if not match:
        return None

    owner, repo = match.groups()
    repo = repo.replace('.git', '').split('/')[0]

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {token}'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            license_info = data.get('license')
            if license_info:
                return {
                    'license': license_info.get('key', 'unknown'),
                    'license_name': license_info.get('name', 'Unknown'),
                    'license_url': license_info.get('url', ''),
                    'repo_stars': data.get('stargazers_count', 0),
                    'repo_forks': data.get('forks_count', 0),
                    'status': 'success'
                }
            else:
                return {
                    'license': 'none',
                    'license_name': 'No License',
                    'license_url': '',
                    'repo_stars': data.get('stargazers_count', 0),
                    'repo_forks': data.get('forks_count', 0),
                    'status': 'success'
                }
        elif response.status_code == 404:
            return {'status': 'failed', 'license': 'not_found'}
        elif response.status_code == 403:
            if 'rate limit' in response.text.lower():
                return {'status': 'rate_limited'}
            return {'status': 'failed', 'license': 'forbidden'}
        else:
            return {'status': 'failed', 'license': f'error_{response.status_code}'}
    except requests.exceptions.Timeout:
        return {'status': 'failed', 'license': 'timeout'}
    except Exception as e:
        return {'status': 'failed', 'license': 'error', 'error': str(e)}

def process_github_files():
    """处理GitHub来源的文件"""
    base_dir = Path('stream2graph_dataset/final_100percent_real/github')

    # 收集需要修复的文件
    files_to_fix = []
    for json_file in base_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            license_key = data.get('license', '')
            # 只处理需要修复的
            if license_key in ['rate_limited', 'error', 'other', 'error_403', 'error_404', 'unknown']:
                files_to_fix.append({
                    'file': json_file,
                    'data': data,
                    'current_license': license_key
                })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    print(f"Found {len(files_to_fix)} GitHub files to fix")

    stats = {'total': len(files_to_fix), 'success': 0, 'failed': 0, 'rate_limited': 0, 'by_license': Counter()}

    for i, item in enumerate(files_to_fix):
        json_file = item['file']
        data = item['data']

        source_url = data.get('source_url', '')
        if not source_url or 'github.com' not in source_url:
            continue

        print(f"[{i+1}/{len(files_to_fix)}] {data.get('id', 'unknown')}...", end=' ')

        license_info = get_github_license(source_url, GITHUB_TOKEN)

        if license_info.get('status') == 'rate_limited':
            print("RATE LIMITED - Waiting 60 seconds...")
            stats['rate_limited'] += 1
            time.sleep(60)
            license_info = get_github_license(source_url, GITHUB_TOKEN)

        if license_info and license_info.get('status') == 'success':
            data['license'] = license_info['license']
            data['license_name'] = license_info['license_name']
            data['license_url'] = license_info['license_url']
            data['repo_stars'] = license_info['repo_stars']
            data['repo_forks'] = license_info['repo_forks']

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            stats['success'] += 1
            stats['by_license'][license_info['license']] += 1
            print(f"OK -> {license_info['license']}")
        else:
            stats['failed'] += 1
            print(f"FAILED -> {license_info.get('license', 'unknown')}")

        # 每100个请求等待一下
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(files_to_fix)}, Success: {stats['success']}")
            time.sleep(2)
        else:
            time.sleep(0.1)

    print("\nGitHub Fix Summary:")
    print(f"  Total: {stats['total']}")
    print(f"  Success: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Rate Limited: {stats['rate_limited']}")
    print("  License distribution:")
    for lic, count in stats['by_license'].most_common():
        print(f"    {lic}: {count}")

    return stats

def process_gitlab_files():
    """处理GitLab来源的文件 - 标记为gitlab_repo并尝试获取信息"""
    base_dir = Path('stream2graph_dataset/final_100percent_real/gitlab')

    files_to_fix = []
    for json_file in base_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            license_key = data.get('license', '')
            if license_key in ['rate_limited', 'error', 'other', 'gitlab_unknown', 'unknown']:
                files_to_fix.append({'file': json_file, 'data': data})
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    print(f"\nFound {len(files_to_fix)} GitLab files to fix")

    fixed = 0
    for item in files_to_fix:
        data = item['data']
        # 对于GitLab数据，我们无法轻易获取许可证，标记为gitlab_repo
        if data.get('license') in ['error', 'rate_limited', 'gitlab_unknown', 'unknown']:
            data['license'] = 'gitlab_repo'
            data['license_name'] = 'GitLab Repository (refer to original repo)'
            with open(item['file'], 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            fixed += 1

    print(f"Fixed {fixed} GitLab files")
    return {'total': len(files_to_fix), 'fixed': fixed}

def process_other_files():
    """处理Other来源的文件 - 尝试从URL推断来源"""
    base_dir = Path('stream2graph_dataset/final_100percent_real/other')

    files_to_fix = []
    for json_file in base_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            license_key = data.get('license', '')
            if license_key in ['rate_limited', 'error', 'other', 'unknown']:
                files_to_fix.append({'file': json_file, 'data': data})
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    print(f"\nFound {len(files_to_fix)} Other files to check")

    # 尝试从URL推断来源并获取许可证
    github_fixed = 0
    other_fixed = 0

    for item in files_to_fix:
        data = item['data']
        source_url = data.get('source_url', '')

        if 'github.com' in source_url:
            license_info = get_github_license(source_url, GITHUB_TOKEN)
            if license_info and license_info.get('status') == 'success':
                data['license'] = license_info['license']
                data['license_name'] = license_info['license_name']
                data['license_url'] = license_info['license_url']
                data['repo_stars'] = license_info['repo_stars']
                data['repo_forks'] = license_info['repo_forks']
                data['source'] = 'github'  # 更新来源

                with open(item['file'], 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                github_fixed += 1
                time.sleep(0.1)
        else:
            # 对于其他来源，标记为unknown_source
            data['license'] = 'unknown_source'
            data['license_name'] = 'Unknown Source (refer to original URL)'
            with open(item['file'], 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            other_fixed += 1

    print(f"Fixed {github_fixed} GitHub URLs from Other category")
    print(f"Marked {other_fixed} as unknown_source")
    return {'total': len(files_to_fix), 'github_fixed': github_fixed, 'other_fixed': other_fixed}

def generate_final_report():
    """生成最终的许可证报告"""
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    stats = {'total': 0, 'by_license': Counter(), 'by_source': {}}

    for source_dir in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source_dir
        if not dir_path.exists():
            continue

        stats['by_source'][source_dir] = Counter()

        for json_file in dir_path.glob('*.json'):
            stats['total'] += 1
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lic = data.get('license', 'MISSING')
                stats['by_license'][lic] += 1
                stats['by_source'][source_dir][lic] += 1
            except Exception as e:
                print(f"Error reading {json_file}: {e}")

    print("\n" + "="*60)
    print("FINAL LICENSE REPORT")
    print("="*60)
    print(f"Total samples: {stats['total']}")
    print("\nTop 20 License Distribution:")
    for lic, count in stats['by_license'].most_common(20):
        print(f"  {lic}: {count} ({count/stats['total']*100:.1f}%)")

    # 计算有效许可证比例（排除error, none, rate_limited等）
    invalid_licenses = {'error', 'none', 'rate_limited', 'not_found', 'unknown', 'unknown_source',
                       'error_403', 'error_404', 'other', 'timeout'}
    valid_count = sum(c for lic, c in stats['by_license'].items() if lic not in invalid_licenses)
    print(f"\nValid licenses: {valid_count} ({valid_count/stats['total']*100:.1f}%)")
    print(f"Invalid/Error: {stats['total'] - valid_count} ({(stats['total']-valid_count)/stats['total']*100:.1f}%)")

    # 保存报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'total': stats['total'],
        'valid_count': valid_count,
        'valid_percentage': valid_count/stats['total']*100,
        'by_license': dict(stats['by_license']),
        'by_source': {k: dict(v) for k, v in stats['by_source'].items()}
    }

    with open('final_license_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\nReport saved to: final_license_report.json")

if __name__ == '__main__':
    print("="*60)
    print("Stream2Graph License Fix Tool")
    print("="*60)
    print(f"GitHub Token: {'Set (may be expired)' if GITHUB_TOKEN else 'Not Set'}")
    print()

    # 处理GitHub文件
    print("Processing GitHub files...")
    github_stats = process_github_files()

    # 处理GitLab文件
    print("\nProcessing GitLab files...")
    gitlab_stats = process_gitlab_files()

    # 处理Other文件
    print("\nProcessing Other files...")
    other_stats = process_other_files()

    # 生成最终报告
    print("\nGenerating final report...")
    generate_final_report()

    print("\n" + "="*60)
    print("License fix process completed!")
    print("="*60)
