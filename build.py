#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aoyagi blog — ビルドスクリプト

articles/*.md (YAML frontmatter付き) を全部スキャンして articles.json を
自動生成する。articles.json は「成果物」であり、これを直接手で編集する
ことは想定しない — 記事の情報はすべて Markdown ファイル側の frontmatter が
Single Source of Truth。

Usage:
    python build.py
"""

import json
import re
import sys
from pathlib import Path

# Windows環境でコンソールの既定エンコーディング（cp932等）と絵文字/日本語の
# 出力がぶつかってcrashしないようにする保険
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("❌ PyYAMLが必要です: pip install -r requirements.txt")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent
ARTICLES_DIR = REPO_ROOT / "articles"
ARTICLES_JSON = REPO_ROOT / "articles.json"
TAGS_JSON = REPO_ROOT / "tags.json"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n(.*)$", re.DOTALL)


def slugify(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^\w\-]", "", s)
    return s[:50] or "tag"


def load_tags() -> list[dict]:
    if TAGS_JSON.exists():
        return json.loads(TAGS_JSON.read_text(encoding="utf-8"))
    return []


def save_tags(tags: list[dict]) -> None:
    tags = sorted(tags, key=lambda t: t["name"])
    with open(TAGS_JSON, "w", encoding="utf-8") as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


def parse_article(md_path: Path) -> dict | None:
    """1つのMarkdownファイルをパースしてメタデータを返す"""
    raw = md_path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)

    if not match:
        print(f"⚠️  {md_path.name}: frontmatterが見つかりません。スキップします。")
        return None

    front_raw, body = match.groups()

    try:
        meta = yaml.safe_load(front_raw) or {}
    except yaml.YAMLError as e:
        print(f"⚠️  {md_path.name}: frontmatterのパースに失敗しました ({e})。スキップします。")
        return None

    title = meta.get("title")
    date = meta.get("date")
    tags = meta.get("tags") or []

    if not title or not date:
        print(f"⚠️  {md_path.name}: title/dateが不足しています。スキップします。")
        return None

    # dateはYAMLがdatetime.dateにパースすることがあるので文字列化
    date = str(date)

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    article_id = md_path.stem

    # 本文の最初の非空行をざっくり抜粋（一覧の説明文などに使えるように）
    excerpt = ""
    for line in body.strip().split("\n"):
        line = line.strip().lstrip("#").strip()
        if line:
            excerpt = line[:120]
            break

    return {
        "id": article_id,
        "title": title,
        "date": date,
        "tags": tags,
        "excerpt": excerpt,
        "file": f"articles/{md_path.name}",
    }


def sync_tags(articles: list[dict]) -> list[dict]:
    """記事のfrontmatterで使われているタグIDをtags.jsonに反映する。

    - 既にtags.jsonにあるタグは名前などをそのまま保持する（エディタで作った
      表示名を上書きしない）
    - 記事の中で使われているが tags.json に無いタグIDは、id=name として
      自動登録する（直接.mdを手書きした場合の保険）
    - どの記事からも参照されなくなったタグは削除せず残す（先に作っておいて
      後で紐づける運用ができるように）
    """
    existing = {t["id"]: t for t in load_tags()}

    for article in articles:
        for tag_id in article["tags"]:
            if tag_id not in existing:
                existing[tag_id] = {"id": tag_id, "name": tag_id}

    tags = list(existing.values())
    save_tags(tags)
    return tags


def build() -> list[dict]:
    ARTICLES_DIR.mkdir(exist_ok=True)

    articles = []
    for md_path in sorted(ARTICLES_DIR.glob("*.md")):
        article = parse_article(md_path)
        if article:
            articles.append(article)

    articles.sort(key=lambda a: a["date"], reverse=True)

    with open(ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    sync_tags(articles)

    return articles


def main():
    articles = build()
    print(f"✅ articles.json を更新しました（{len(articles)}件）")
    for a in articles:
        print(f"   - {a['date']}  {a['title']}")


if __name__ == "__main__":
    main()
