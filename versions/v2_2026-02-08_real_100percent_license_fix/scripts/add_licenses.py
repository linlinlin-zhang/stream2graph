#!/usr/bin/env python3
"""
为数据集补充许可证信息
"""
import json
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# GitHub API Token（从环境变量获取）
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

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
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
                    'repo_name': repo
                }
            else:
                return {
                    'license': 'none',
                    'license_name': 'No License',
                    'license_url': '',
                    'repo_stars': data.get('stargazers_count', 0),
                    'repo_forks': data.get('forks_count', 0),
                    'repo_owner': owner,
                    'repo_name': repo
                }
        elif response.status_code == 404:
            return {'license': 'not_found', 'license_name': 'Repository Not Found'}
        elif response.status_code == 403:
            return {'license': 'rate_limited', 'license_name': 'API Rate Limited'}
        else:
            return {'license': f'error_{response.status_code}', 'license_name': f'Error {response.status_code}'}
    except Exception as e:
        return {'license': 'error', 'license_name': str(e)}

def process_file(filepath):
    """处理单个文件，添加许可证信息"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 如果已有许可证字段，跳过
        if 'license' in data and data['license'] not in ['', 'unknown']:
            return {'status': 'skipped', 'file': filepath, 'license': data['license']}

        source = data.get('source', '')
        source_url = data.get('source_url', '')

        license_info = None

        if source == 'github' or 'github.com' in source_url:
            license_info = get_github_license(source_url)
            time.sleep(0.5)  # 避免速率限制
        elif source == 'huggingface':
            license_info = {
                'license': 'huggingface_dataset',
                'license_name': 'HuggingFace Dataset (refer to original dataset license)',
                'source_dataset': 'codeparrot/github-jupyter-text-code-pairs'
            }
        elif source == 'gitlab':
            # GitLab许可证获取较复杂，暂时标记
            license_info = {'license': 'gitlab_unknown', 'license_name': 'GitLab Repository (license unknown)'}
        else:
            # 尝试检测GitHub链接
            if 'github.com' in source_url:
                license_info = get_github_license(source_url)
                time.sleep(0.5)
            else:
                license_info = {'license': 'unknown', 'license_name': 'Unknown Source'}

        if license_info:
            data.update(license_info)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {'status': 'updated', 'file': filepath, 'license': license_info.get('license', 'unknown')}

        return {'status': 'failed', 'file': filepath, 'reason': 'Could not determine license'}

    except Exception as e:
        return {'status': 'error', 'file': filepath, 'error': str(e)}

def main():
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    # 收集所有JSON文件
    all_files = []
    for source_dir in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source_dir
        if dir_path.exists():
            all_files.extend(list(dir_path.glob('*.json')))

    print(f"找到 {len(all_files)} 个样本文件")
    print(f"GitHub Token: {'已设置' if GITHUB_TOKEN else '未设置（将受到速率限制）'}")

    # 统计
    stats = {
        'total': len(all_files),
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'error': 0,
        'by_license': {}
    }

    # 处理文件
    print("\n开始处理...")
    for i, filepath in enumerate(all_files):
        result = process_file(filepath)

        stats[result['status']] = stats.get(result['status'], 0) + 1

        if result['status'] == 'updated':
            license_key = result.get('license', 'unknown')
            stats['by_license'][license_key] = stats['by_license'].get(license_key, 0) + 1

        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1}/{len(all_files)} 文件...")
            print(f"  更新: {stats['updated']}, 跳过: {stats['skipped']}, 失败: {stats['failed']}, 错误: {stats['error']}")

    # 生成报告
    print("\n" + "="*50)
    print("许可证补充完成报告")
    print("="*50)
    print(f"总计: {stats['total']}")
    print(f"已更新: {stats['updated']}")
    print(f"已跳过(已有许可证): {stats['skipped']}")
    print(f"失败: {stats['failed']}")
    print(f"错误: {stats['error']}")
    print("\n许可证分布:")
    for license_key, count in sorted(stats['by_license'].items(), key=lambda x: -x[1]):
        print(f"  {license_key}: {count}")

    # 保存统计报告
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': stats
    }

    with open('license_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n报告已保存到 license_report.json")

if __name__ == '__main__':
    main()
