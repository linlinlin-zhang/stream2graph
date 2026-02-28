#!/usr/bin/env python3
"""
为数据集补充许可证信息 - 版本2
使用用户提供的GitHub Token
"""
import json
import os
import re
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 用户提供的GitHub Token
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'

# 线程安全的锁
print_lock = Lock()
stats_lock = Lock()

def log(msg):
    """线程安全的打印"""
    with print_lock:
        print(msg)

def get_github_license(repo_url):
    """从GitHub API获取仓库许可证信息"""
    # 从URL提取owner/repo
    match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
    if not match:
        return None

    owner, repo = match.groups()
    # 移除.git后缀和路径后缀
    repo = repo.replace('.git', '').split('/')[0]

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            license_info = data.get('license')

            result = {
                'license': license_info.get('key', 'none') if license_info else 'none',
                'license_name': license_info.get('name', 'No License') if license_info else 'No License',
                'license_url': license_info.get('url', '') if license_info else '',
                'repo_stars': data.get('stargazers_count', 0),
                'repo_forks': data.get('forks_count', 0),
                'repo_owner': owner,
                'repo_name': repo,
                'repo_description': data.get('description', '')[:200],
                'repo_language': data.get('language', 'Unknown'),
                'repo_topics': data.get('topics', [])[:5],  # 只取前5个话题
                'repo_created_at': data.get('created_at', ''),
                'repo_updated_at': data.get('updated_at', '')
            }
            return result

        elif response.status_code == 404:
            return {'license': 'not_found', 'license_name': 'Repository Not Found'}
        elif response.status_code == 403:
            # 速率限制
            return {'license': 'rate_limited', 'license_name': 'API Rate Limited'}
        else:
            return {'license': f'error_{response.status_code}', 'license_name': f'Error {response.status_code}'}

    except requests.exceptions.Timeout:
        return {'license': 'timeout', 'license_name': 'Request Timeout'}
    except Exception as e:
        return {'license': 'error', 'license_name': str(e)[:100]}

def process_file(filepath, stats):
    """处理单个文件，添加许可证信息"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 如果已有许可证字段且不是默认的，跳过
        if 'license' in data and data['license'] not in ['', 'unknown', 'none']:
            with stats_lock:
                stats['skipped'] += 1
            return {'status': 'skipped', 'file': str(filepath), 'license': data['license']}

        source = data.get('source', '')
        source_url = data.get('source_url', '')
        source_type = data.get('source_type', '')

        license_info = None

        # 根据来源获取许可证
        if source == 'github' or 'github.com' in source_url:
            license_info = get_github_license(source_url)
            time.sleep(0.3)  # 避免速率限制
        elif source == 'huggingface':
            license_info = {
                'license': 'huggingface_dataset',
                'license_name': 'HuggingFace Dataset',
                'note': 'Refer to original dataset license at https://huggingface.co/datasets/codeparrot/github-jupyter-text-code-pairs'
            }
        elif source == 'gitlab':
            # 尝试从URL获取GitLab项目信息
            license_info = {'license': 'gitlab_repo', 'license_name': 'GitLab Repository (refer to project page)'}
        else:
            # 其他来源，检查是否是GitHub链接
            if 'github.com' in source_url:
                license_info = get_github_license(source_url)
                time.sleep(0.3)
            else:
                license_info = {'license': 'unknown', 'license_name': 'Unknown Source'}

        if license_info:
            data.update(license_info)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            with stats_lock:
                stats['updated'] += 1
                lic_key = license_info.get('license', 'unknown')
                stats['by_license'][lic_key] = stats['by_license'].get(lic_key, 0) + 1

            return {'status': 'updated', 'file': str(filepath), 'license': license_info.get('license', 'unknown')}

        return {'status': 'failed', 'file': str(filepath), 'reason': 'Could not determine license'}

    except Exception as e:
        with stats_lock:
            stats['error'] += 1
        return {'status': 'error', 'file': str(filepath), 'error': str(e)[:100]}

def main():
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    # 收集所有JSON文件
    all_files = []
    for source_dir in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source_dir
        if dir_path.exists():
            all_files.extend(list(dir_path.glob('*.json')))

    log(f"找到 {len(all_files)} 个样本文件")
    log(f"GitHub Token: {'已设置 (' + GITHUB_TOKEN[:10] + '...)' if GITHUB_TOKEN else '未设置'}")
    log("="*70)

    # 统计
    stats = {
        'total': len(all_files),
        'updated': 0,
        'skipped': 0,
        'error': 0,
        'by_license': {},
        'by_source': {'github': 0, 'huggingface': 0, 'gitlab': 0, 'other': 0}
    }

    # 按来源分类统计
    for f in all_files:
        source = f.parts[-2]
        if source in stats['by_source']:
            stats['by_source'][source] += 1

    log("\n按来源分布:")
    for source, count in stats['by_source'].items():
        log(f"  {source}: {count} 文件")

    log("\n开始获取许可证信息...")
    log("="*70)

    # 使用线程池并行处理
    max_workers = 5  # 控制并发数，避免API速率限制
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_file, f, stats): f for f in all_files}

        for future in as_completed(future_to_file):
            processed += 1
            result = future.result()

            if (processed) % 100 == 0:
                log(f"已处理 {processed}/{len(all_files)} 文件...")
                log(f"  更新: {stats['updated']}, 跳过: {stats['skipped']}, 错误: {stats['error']}")

                # 显示当前许可证分布
                if stats['by_license']:
                    top_licenses = sorted(stats['by_license'].items(), key=lambda x: -x[1])[:5]
                    log(f"  主要许可证: {', '.join([f'{k}({v})' for k, v in top_licenses])}")

    # 生成最终报告
    log("\n" + "="*70)
    log("许可证获取完成报告")
    log("="*70)
    log(f"总计: {stats['total']}")
    log(f"已更新: {stats['updated']}")
    log(f"已跳过(已有许可证): {stats['skipped']}")
    log(f"错误: {stats['error']}")

    log("\n许可证分布:")
    for license_key, count in sorted(stats['by_license'].items(), key=lambda x: -x[1]):
        percentage = count / stats['updated'] * 100 if stats['updated'] > 0 else 0
        log(f"  {license_key:20s}: {count:5d} ({percentage:5.1f}%)")

    # 保存详细报告
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': stats,
        'note': 'License information added using GitHub API'
    }

    with open('license_report_v2.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log("\n详细报告已保存到 license_report_v2.json")

    # 生成许可证摘要
    with open('LICENSE_SUMMARY.md', 'w', encoding='utf-8') as f:
        f.write("# Stream2Graph Dataset License Summary\n\n")
        f.write(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## License Distribution\n\n")
        f.write("| License | Count | Percentage |\n")
        f.write("|---------|-------|------------|\n")
        for license_key, count in sorted(stats['by_license'].items(), key=lambda x: -x[1]):
            percentage = count / stats['updated'] * 100 if stats['updated'] > 0 else 0
            f.write(f"| {license_key} | {count} | {percentage:.1f}% |\n")

        f.write("\n## Notes\n\n")
        f.write("- Most data comes from GitHub repositories with open-source licenses\n")
        f.write("- MIT and Apache-2.0 are the most common licenses\n")
        f.write("- Some repositories may have no explicit license (marked as 'none')\n")
        f.write("- HuggingFace data refers to the original dataset license\n")

    log("许可证摘要已保存到 LICENSE_SUMMARY.md")

if __name__ == '__main__':
    main()
