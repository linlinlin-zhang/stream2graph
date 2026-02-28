#!/usr/bin/env python3
"""
修复GitHub数据的许可证信息 - 无Token模式（放慢速度避免限速）
"""
import json
import os
import re
import time
import requests
from pathlib import Path
from datetime import datetime

# GitHub API Token（可选，从环境变量获取）
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def get_github_license(repo_url):
    """从GitHub API获取仓库许可证信息"""
    # 从URL提取owner/repo
    match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
    if not match:
        return None

    owner, repo = match.groups()
    # 移除.git后缀如果存在
    repo = repo.replace('.git', '')
    # 移除其他路径部分
    repo = repo.split('/')[0]

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

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
                    'repo_owner': owner,
                    'repo_name': repo,
                    'status': 'success'
                }
            else:
                return {
                    'license': 'none',
                    'license_name': 'No License',
                    'license_url': '',
                    'repo_stars': data.get('stargazers_count', 0),
                    'repo_forks': data.get('forks_count', 0),
                    'repo_owner': owner,
                    'repo_name': repo,
                    'status': 'success'
                }
        elif response.status_code == 404:
            return {'license': 'not_found', 'license_name': 'Repository Not Found', 'status': 'failed'}
        elif response.status_code == 403:
            # 检查是否是速率限制
            if 'rate limit' in response.text.lower() or 'api rate limit' in response.text.lower():
                return {'license': 'rate_limited', 'license_name': 'API Rate Limited', 'status': 'rate_limited', 'retry_after': 60}
            return {'license': 'forbidden', 'license_name': 'Access Forbidden', 'status': 'failed'}
        else:
            return {'license': f'error_{response.status_code}', 'license_name': f'Error {response.status_code}', 'status': 'failed'}
    except requests.exceptions.Timeout:
        return {'license': 'timeout', 'license_name': 'Request Timeout', 'status': 'failed'}
    except Exception as e:
        return {'license': 'error', 'license_name': str(e), 'status': 'failed'}

def process_github_files(limit=None):
    """处理GitHub目录下的所有JSON文件"""
    base_dir = Path('stream2graph_dataset/final_100percent_real/github')

    # 收集需要处理的文件
    files_to_process = []
    for json_file in base_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            license_key = data.get('license', 'MISSING')
            # 只处理需要修复的
            if license_key in ['error', 'none', 'rate_limited', 'other', 'error_403', 'error_404', 'unknown']:
                files_to_process.append({
                    'file': json_file,
                    'data': data,
                    'current_license': license_key
                })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    if limit:
        files_to_process = files_to_process[:limit]

    print(f"Found {len(files_to_process)} files to process")

    # 统计
    stats = {
        'total': len(files_to_process),
        'success': 0,
        'failed': 0,
        'rate_limited': 0,
        'by_license': {}
    }

    # 处理文件
    for i, item in enumerate(files_to_process):
        json_file = item['file']
        data = item['data']

        source_url = data.get('source_url', '')
        if not source_url or 'github.com' not in source_url:
            print(f"[{i+1}/{len(files_to_process)}] Skip {json_file.name}: No GitHub URL")
            continue

        print(f"[{i+1}/{len(files_to_process)}] Processing {json_file.name}...", end=' ')

        # 获取许可证信息
        license_info = get_github_license(source_url)

        if license_info.get('status') == 'rate_limited':
            print("RATE LIMITED - Waiting 60 seconds...")
            stats['rate_limited'] += 1
            if not GITHUB_TOKEN:
                # 无Token模式，等待更长时间
                time.sleep(60)
                # 重试一次
                license_info = get_github_license(source_url)
                if license_info.get('status') == 'rate_limited':
                    print("Still rate limited, continuing...")
                    continue
            else:
                continue

        if license_info and license_info.get('status') == 'success':
            # 更新数据
            data['license'] = license_info['license']
            data['license_name'] = license_info['license_name']
            data['license_url'] = license_info['license_url']
            data['repo_stars'] = license_info['repo_stars']
            data['repo_forks'] = license_info['repo_forks']
            data['repo_owner'] = license_info['repo_owner']
            data['repo_name'] = license_info['repo_name']

            # 保存文件
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            stats['success'] += 1
            license_key = license_info['license']
            stats['by_license'][license_key] = stats['by_license'].get(license_key, 0) + 1
            print(f"OK -> {license_key}")
        else:
            stats['failed'] += 1
            print(f"FAILED -> {license_info.get('license', 'unknown')}")

        # 无Token模式下，每10个请求等待更长时间以避免限速
        if not GITHUB_TOKEN and (i + 1) % 10 == 0:
            print("  Pausing 5 seconds to avoid rate limit...")
            time.sleep(5)
        else:
            time.sleep(0.5)  # 基础延迟

    # 生成报告
    print("\n" + "="*60)
    print("GitHub License Fix Report")
    print("="*60)
    print(f"Total processed: {stats['total']}")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Rate limited: {stats['rate_limited']}")
    print("\nLicense distribution:")
    for license_key, count in sorted(stats['by_license'].items(), key=lambda x: -x[1]):
        print(f"  {license_key}: {count}")

    # 保存报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'statistics': stats
    }
    with open('github_license_fix_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return stats

if __name__ == '__main__':
    import sys
    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        print(f"Processing first {limit} files only")

    print(f"GitHub Token: {'Set' if GITHUB_TOKEN else 'Not Set (slower mode)'}")
    print("Starting license fix process...\n")

    stats = process_github_files(limit)
