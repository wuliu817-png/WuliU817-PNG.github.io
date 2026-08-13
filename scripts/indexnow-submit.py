#!/usr/bin/env python3
"""IndexNow 提交脚本 — 增量提交 swaplyn.com 新 URL 给 Bing。

用法:
    python3 scripts/indexnow-submit.py            # 增量：只提交 sitemap 中未提交过的新 URL
    python3 scripts/indexnow-submit.py --all      # 全量：重新提交 sitemap 所有 URL
    python3 scripts/indexnow-submit.py URL1 URL2  # 额外追加指定 URL（一并增量提交）

状态文件:
    scripts/.indexnow-submitted.txt  # 已提交过的 URL（每行一个），首次运行自动创建

说明:
    - IndexNow 允许重复提交，不扣分；正常用增量模式即可。
    - 每次发新文章、部署上线后跑一次，会自动识别并只推新 URL。
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error

KEY = "e32080cbf15b453e91e930fa35782f54"
HOST = "swaplyn.com"
KEY_LOCATION = f"https://swaplyn.com/{KEY}.txt"
SITEMAP = "https://swaplyn.com/sitemap.xml"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".indexnow-submitted.txt")


def fetch_sitemap() -> list:
    with urllib.request.urlopen(SITEMAP, timeout=30) as r:
        body = r.read().decode("utf-8")
    # [^<]* 而非 [^<]+，确保首页 https://swaplyn.com/ 也能被捕获
    urls = re.findall(r"<loc>(https://swaplyn\.com/[^<]*)</loc>", body)
    return sorted(set(urls))


def load_state() -> set:
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE) as f:
        return set(l.strip() for l in f if l.strip())


def save_state(urls: set) -> None:
    with open(STATE_FILE, "w") as f:
        for u in sorted(urls):
            f.write(u + "\n")


def submit(urls: list) -> tuple:
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        print(f"❌ 网络错误: {e.reason}")
        sys.exit(1)


def main() -> None:
    force_all = "--all" in sys.argv
    extra = [u for u in sys.argv[1:] if u.startswith("http")]

    sitemap_urls = fetch_sitemap()
    submitted = load_state()

    if force_all:
        to_submit = sorted(set(sitemap_urls + extra))
        print(f"🔄 全量模式：sitemap 共 {len(sitemap_urls)} 个，提交 {len(to_submit)} 个")
    else:
        new_urls = sorted(set(sitemap_urls + extra) - submitted)
        if not new_urls:
            print(f"✅ 无新 URL（sitemap {len(sitemap_urls)} 个均已提交过），跳过")
            return
        to_submit = new_urls
        print(f"📥 增量模式：sitemap {len(sitemap_urls)} 个，本次新 URL {len(to_submit)} 个")
        for u in to_submit:
            print(f"   + {u}")

    status, body = submit(to_submit)
    print(f"📤 提交完成: HTTP {status}")
    if body:
        print(f"   响应体: {body.strip()}")

    code_msg = {
        200: "✅ 成功",
        202: "✅ 成功（已接受）",
        400: "❌ 请求格式错误",
        403: "❌ key 无效（检查 key 文件是否上线且内容一致）",
        422: "❌ URL 不属于该 host",
        429: "❌ 请求过多",
    }
    print(f"   结果: {code_msg.get(status, '未知状态码')}")

    if status in (200, 202):
        submitted.update(to_submit)
        save_state(submitted)
        print(f"💾 已记录 {len(submitted)} 个已提交 URL 到状态文件")


if __name__ == "__main__":
    main()
