import json
import os
import requests
import time
from pathlib import Path
from hashlib import md5
from datetime import datetime

class DeepIndustrialCollector:
    def __init__(self):
        self.base_dir = Path('/home/lin-server/pictures/stream2graph_dataset/v4_industrial_source')
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.token = 'YOUR_GITHUB_TOKEN'
        self.headers = {'Authorization': f'token {self.token}', 'Accept': 'application/vnd.github.v3+json'}
        self.log_file = Path('/home/lin-server/pictures/NEW_COLLECTION_COMPLIANCE.md')
        
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# Stream2Graph 新增合规采集日志 (补全至 8,000)\n\n")
                f.write("| 采集时间 | 仓库 | 许可证 | 类型 | 结果 |\n")
                f.write("| --- | --- | --- | --- | --- |\n")

    def log_success(self, repo, license, dtype, sid):
        line = f"| {datetime.now().strftime('%H:%M:%S')} | {repo} | {license} | {dtype} | ✅ {sid} |\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line)

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=10)
            return resp.status_code == 200
        except: return False

    def search_and_collect(self, query, limit=500):
        print(f"--- 正在 GitHub 检索合规仓库: {query} ---")
        url = "https://api.github.com/search/code"
        page = 1
        collected = 0
        while collected < limit and page <= 30:
            # 检查全局真实数据数量是否已达标 (2447 + 553 = 3000)
            if len(list(self.base_dir.glob('*.json'))) >= 553:
                print("--- 目标：3000条真实数据已全部达成！ ---")
                return limit # 提前结束
                
            params = {'q': f'{query} language:mermaid', 'per_page': 30, 'page': page}
            # 如果 language:mermaid 结果较少，可以再跑一轮 extension:mmd，不过这里先用官方语言标签
            # 也可以用 OR: f'{query} (extension:mmd OR extension:mermaid)'
            params = {'q': f'{query} extension:mmd OR extension:mermaid', 'per_page': 30, 'page': page}
            try:
                resp = requests.get(url, headers=self.headers, params=params, timeout=20)
                if resp.status_code == 200:
                    items = resp.json().get('items', [])
                    for item in items:
                        if collected >= limit: break
                        repo_name = item['repository']['full_name']
                        r_url = f"https://api.github.com/repos/{repo_name}"
                        r_resp = requests.get(r_url, headers=self.headers, timeout=10)
                        license = r_resp.json().get('license', {}).get('key', 'none') if r_resp.status_code == 200 else 'none'
                        if license != 'none':
                            raw_url = item['html_url'].replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                            content = requests.get(raw_url, timeout=10).text
                            sid = f"gh_ind_{md5(content.encode()).hexdigest()[:10]}"
                            if (self.base_dir / f"{sid}.json").exists():
                                collected += 1
                                continue
                                
                            if len(content) > 50 and self.check_compilability(content):
                                sample = {'id': sid, 'source': 'github_industrial', 'repo': repo_name, 'license': license, 'code': content, 'diagram_type': query, 'collected_at': datetime.now().isoformat()}
                                with open(self.base_dir / f"{sid}.json", 'w', encoding='utf-8') as sf: json.dump(sample, sf, ensure_ascii=False, indent=2)
                                self.log_success(repo_name, license, query, sid)
                                collected += 1
                                print(f"  [+] 已入库: {sid} ({license})")
                        time.sleep(0.5)
                    page += 1
                elif resp.status_code == 403:
                    print("Rate limited. Sleep 60s.")
                    time.sleep(60)
                else: break
            except: break
        return collected

if __name__ == "__main__":
    import random
    collector = DeepIndustrialCollector()
    
    keywords = [
        'architecture', 'sequence', 'er', 'state', 'gantt', 'class', 
        'pie', 'journey', 'mindmap', 'timeline', 'flowchart', 'graph',
        'subgraph', 'participant', 'node', 'actor', 'loop', 'alt'
    ]
    size_ranges = [
        'size:50..150', 'size:150..250', 'size:250..400', 
        'size:400..600', 'size:600..900', 'size:900..1500', 'size:>1500'
    ]
    
    while True:
        # 如果已经集齐 553 条 (总共 3000 条)
        if len(list(collector.base_dir.glob('*.json'))) >= 553:
            print("--- 目标：3000条真实数据已全部达成！ ---")
            break
            
        kw = random.choice(keywords)
        sr = random.choice(size_ranges)
        query = f"{kw} {sr}"
        
        collector.search_and_collect(query, limit=200)
        time.sleep(2) # 防止单次循环过快导致频繁 403
