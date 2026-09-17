#!/usr/bin/env python3
"""拉取 GSC (Google Search Console) 数据：swaplyn.com 查询词 + 页面 + 日期趋势。

用法: python3 scripts/gsc-pull.py
输出: data/gsc_swaplyn_latest.json (28 天窗口)
"""
import json
import sys
import datetime

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

KEY_FILE = "/Users/yangwenlin/Downloads/clean-skill-503811-c4-38eadbb86283.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITE = "https://swaplyn.com/"
PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"


def get_token():
    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=SCOPES
    )
    # 用 requests.Session 手动走代理（google-auth 默认 httplib2 不吃系统代理）
    session = requests.Session()
    session.proxies.update(PROXIES)
    req = google.auth.transport.requests.Request(session=session)
    creds.refresh(req)
    return creds.token


def query_gsc(token, dimensions, start_date, end_date, row_limit=5000):
    session = requests.Session()
    session.proxies.update(PROXIES)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "startRow": 0,
    }
    url = API.format(site=SITE.replace("/", "%2F"))
    r = session.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def main():
    today = datetime.date.today()
    end = today - datetime.timedelta(days=1)      # GSC 有 2~3 天延迟
    start = end - datetime.timedelta(days=27)      # 28 天窗口
    start_s, end_s = start.isoformat(), end.isoformat()

    token = get_token()

    # 查询词
    q = query_gsc(token, ["query"], start_s, end_s)
    queries = [
        {
            "keys": row["keys"],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": round(row["ctr"], 4),
            "position": round(row["position"], 1),
        }
        for row in q.get("rows", [])
    ]
    queries.sort(key=lambda x: -x["impressions"])

    # 页面
    p = query_gsc(token, ["page"], start_s, end_s)
    pages = [
        {
            "keys": row["keys"],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": round(row["ctr"], 4),
            "position": round(row["position"], 1),
        }
        for row in p.get("rows", [])
    ]
    pages.sort(key=lambda x: -x["impressions"])

    # 日期趋势
    d = query_gsc(token, ["date"], start_s, end_s, row_limit=1000)
    dates = [
        {
            "keys": row["keys"],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": round(row["ctr"], 4),
            "position": round(row["position"], 1),
        }
        for row in d.get("rows", [])
    ]
    dates.sort(key=lambda x: x["keys"][0])

    def total(rows):
        clicks = sum(r["clicks"] for r in rows)
        imps = sum(r["impressions"] for r in rows)
        return clicks, imps

    q_clicks, q_imps = total(queries)
    overview = {
        "clicks": q_clicks,
        "impressions": q_imps,
        "ctr": round(q_clicks / q_imps, 4) if q_imps else 0,
        "position": round(
            sum(r["impressions"] * r["position"] for r in queries) / q_imps, 1
        )
        if q_imps
        else 0,
        "range": f"{start_s} ~ {end_s}",
    }

    out = {
        "fetched": today.isoformat(),
        "site": SITE,
        "overview": overview,
        "queries": queries,
        "pages": pages,
        "dates": dates,
    }
    with open("data/gsc_swaplyn_latest.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(json.dumps(overview, ensure_ascii=False, indent=1))
    print(f"\nqueries={len(queries)} pages={len(pages)} dates={len(dates)}")
    print("saved -> data/gsc_swaplyn_latest.json")


if __name__ == "__main__":
    main()
