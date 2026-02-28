#!/usr/bin/env python3
"""
批量修复剩余的GitHub许可证
使用多线程加速处理
"""
import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'
INVALID_LICENSES = {'error', 'rate_limited', 'unknown', 'other', 'timeout',
                    'not_found', 'forbidden', 'error_403', 'error_404'}

class LicenseFixer:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}'
        }
        self.stats = {'success': 0, 'failed': 0, 'rate_limited': 0}
        self.rate_limit_remaining = 5000

    def get_repo_info(self, owner, repo):
        """获取仓库信息"""
        url = f'https://api.github.com/repos/{owner}/{repo}'
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))

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
                        'repo_stars': data.get('stargazers_count', 0),
                        'repo_forks': data.get('forks_count', 0),
                        'status': 'success'
                    }
            elif response.status_code == 404:
                return {'status': 'failed', 'license': 'not_found'}
            elif response.status_code == 403:
                return {'status': 'rate_limited'}
            else:
                return {'status': 'failed', 'license': f'error_{response.status_code}'}
        except Exception as e:
            return {'status': 'failed', 'license': 'error', 'error': str(e)}

    def extract_repo_info(self, url):
        """从URL提取仓库信息"""
        match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
        if not match:
            return None, None
        owner, repo = match.groups()
        repo = repo.replace('.git', '').split('/')[0]
        return owner, repo

    def process_file(self, file_info):
        """处理单个文件"""
        json_file, data = file_info

        source_url = data.get('source_url', '')
        owner, repo = self.extract_repo_info(source_url)

        if not owner or not repo:
            return {'status': 'skipped'}

        # 获取许可证信息
        license_info = self.get_repo_info(owner, repo)

        if license_info.get('status') == 'rate_limited':
            return {'status': 'rate_limited'}

        if license_info.get('status') == 'success':
            # 更新数据
            data['license'] = license_info['license']
            data['license_name'] = license_info['license_name']
            data['license_url'] = license_info['license_url']
            data['repo_stars'] = license_info['repo_stars']
            data['repo_forks'] = license_info['repo_forks']

            # 保存文件
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return {'status': 'success', 'license': license_info['license']}
        else:
            return {'status': 'failed', 'license': license_info.get('license', 'unknown')}

def main():
    print("="*60)
    print("批量修复剩余GitHub许可证")
    print("="*60)

    base_dir = Path('stream2graph_dataset/final_100percent_real/github')
    fixer = LicenseFixer(GITHUB_TOKEN)

    # 收集需要修复的文件
    files_to_fix = []
    for json_file in base_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            license_key = data.get('license', '')
            if license_key in INVALID_LICENSES:
                files_to_fix.append((json_file, data))
        except Exception as e:
            pass

    print(f"找到 {len(files_to_fix)} 个需要修复的文件\n")

    if not files_to_fix:
        print("所有GitHub许可证已修复完成！")
        return

    # 按仓库分组，避免重复请求
    repo_files = {}
    for json_file, data in files_to_fix:
        source_url = data.get('source_url', '')
        owner, repo = fixer.extract_repo_info(source_url)
        if owner and repo:
            repo_key = f"{owner}/{repo}"
            if repo_key not in repo_files:
                repo_files[repo_key] = []
            repo_files[repo_key].append((json_file, data))

    print(f"涉及 {len(repo_files)} 个唯一仓库")

    # 处理每个仓库
    license_cache = {}
    processed = 0
    total = len(files_to_fix)

    for repo_key, file_list in repo_files.items():
        # 检查速率限制
        if fixer.rate_limit_remaining < 10:
            print(f"\n速率限制即将达到，等待60秒...")
            time.sleep(60)
            fixer.rate_limit_remaining = 5000

        owner, repo = repo_key.split('/')

        # 获取许可证信息（每个仓库只请求一次）
        if repo_key not in license_cache:
            license_info = fixer.get_repo_info(owner, repo)
            license_cache[repo_key] = license_info
            time.sleep(0.05)  # 小延迟避免触发限制
        else:
            license_info = license_cache[repo_key]

        # 应用到该仓库的所有文件
        for json_file, data in file_list:
            processed += 1

            if license_info.get('status') == 'rate_limited':
                fixer.stats['rate_limited'] += 1
                continue

            if license_info.get('status') == 'success':
                data['license'] = license_info['license']
                data['license_name'] = license_info.get('license_name', 'Unknown')
                data['license_url'] = license_info.get('license_url', '')
                data['repo_stars'] = license_info.get('repo_stars', 0)
                data['repo_forks'] = license_info.get('repo_forks', 0)

                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                fixer.stats['success'] += 1
            else:
                fixer.stats['failed'] += 1

        # 进度报告
        if processed % 100 == 0:
            print(f"进度: {processed}/{total}, 成功: {fixer.stats['success']}, "
                  f"失败: {fixer.stats['failed']}, 限速: {fixer.stats['rate_limited']}, "
                  f"API剩余: {fixer.rate_limit_remaining}")

    print("\n" + "="*60)
    print("修复完成!")
    print(f"成功: {fixer.stats['success']}")
    print(f"失败: {fixer.stats['failed']}")
    print(f"触发限速: {fixer.stats['rate_limited']}")
    print("="*60)

if __name__ == '__main__':
    main()
