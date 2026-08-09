#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aoyagi blog — ローカル編集サーバー

ブラウザで http://127.0.0.1:5151 を開くと投稿・編集・削除ができる。
保存すると自動で build.py が走って articles.json を更新する。
Git操作は明示的な「Gitにpush」ボタンを押した時だけ行う（保存とは分離）。

Usage:
    python server.py
"""

import re
import secrets
import subprocess
import sys
import webbrowser
from datetime import date
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, request, send_from_directory

import build as build_mod

# Windows環境でコンソールの既定エンコーディング（cp932等）と絵文字/日本語の
# 出力がぶつかってcrashしないようにする保険
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).parent
ARTICLES_DIR = REPO_ROOT / "articles"
PORT = 5151

app = Flask(__name__, static_folder=None)


def generate_id(title: str) -> str:
    """記事IDは常にASCIIの安全なスラッグにする。

    以前はタイトルの日本語文字をそのままIDに使っていたが、それだと
    Git・URL・OSごとの文字コードの扱いの違いでファイル名とarticles.json
    の参照がズレる事故が起きやすい。タイトルは表示用（frontmatterのtitle）
    にそのまま残し、IDはあくまで内部的なファイル名として分離する。
    """
    ascii_only = title.strip().lower().encode("ascii", "ignore").decode("ascii")
    id_str = re.sub(r"[^a-z0-9\-]+", "-", ascii_only).strip("-")
    id_str = id_str[:50]

    if not id_str:
        # タイトルに英数字が無い場合（日本語のみ等）は日付+ランダムIDで代替
        id_str = f"post-{date.today().isoformat()}-{secrets.token_hex(3)}"

    return id_str


def write_article(article_id: str, title: str, article_date: str, tags: list[str], content: str) -> Path:
    tags_yaml = "[" + ", ".join(tags) + "]"
    frontmatter = (
        f"---\n"
        f"title: {title}\n"
        f"date: {article_date}\n"
        f"tags: {tags_yaml}\n"
        f"---\n\n"
        f"{content.strip()}\n"
    )
    path = ARTICLES_DIR / f"{article_id}.md"
    path.write_text(frontmatter, encoding="utf-8")
    return path


# ===== Static: エディタ画面とブログ本体・記事ファイルを配信 =====

@app.route("/")
def editor_page():
    return send_from_directory(REPO_ROOT / "static", "editor.html")


@app.route("/blog/")
def blog_page():
    return send_from_directory(REPO_ROOT, "index.html")


@app.route("/blog/articles.json")
def blog_articles_json():
    return send_from_directory(REPO_ROOT, "articles.json")


@app.route("/blog/tags.json")
def blog_tags_json():
    return send_from_directory(REPO_ROOT, "tags.json")


@app.route("/blog/articles/<path:filename>")
def blog_article_file(filename):
    return send_from_directory(ARTICLES_DIR, filename)


# ===== API =====

@app.route("/api/articles")
def api_list_articles():
    articles = build_mod.build()
    return jsonify(articles)


@app.route("/api/articles/<article_id>")
def api_get_article(article_id):
    path = ARTICLES_DIR / f"{article_id}.md"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": article_id, "raw": path.read_text(encoding="utf-8")})


@app.route("/api/articles", methods=["POST"])
def api_create_or_update_article():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    article_date = (data.get("date") or "").strip() or date.today().isoformat()

    raw_tags = data.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    tags = [t.strip() for t in raw_tags if t and t.strip()]

    content = data.get("content") or ""
    existing_id = data.get("id")  # 編集時はここにidが入る（タイトルが変わってもファイルは同じ）

    if not title:
        return jsonify({"error": "タイトルは必須です"}), 400
    if not tags:
        return jsonify({"error": "タグを1つ以上入力してください"}), 400
    if not content.strip():
        return jsonify({"error": "本文は必須です"}), 400

    article_id = existing_id or generate_id(title)

    # 新規作成時、既に同じIDのファイルがあれば末尾に短い識別子を足して衝突を避ける
    if not existing_id:
        base_id = article_id
        suffix = 1
        while (ARTICLES_DIR / f"{article_id}.md").exists():
            suffix += 1
            article_id = f"{base_id}-{suffix}"

    write_article(article_id, title, article_date, tags, content)
    articles = build_mod.build()

    return jsonify({"ok": True, "id": article_id, "articles": articles})


@app.route("/api/articles/<article_id>", methods=["DELETE"])
def api_delete_article(article_id):
    path = ARTICLES_DIR / f"{article_id}.md"
    if path.exists():
        path.unlink()
    articles = build_mod.build()
    return jsonify({"ok": True, "articles": articles})


@app.route("/api/tags")
def api_list_tags():
    return jsonify(build_mod.load_tags())


@app.route("/api/tags", methods=["POST"])
def api_create_tag():
    """新しいタグを記事に紐づける前に単独で作成する。既に同名/同IDのタグが
    あればそれをそのまま返す（重複作成しない）。"""
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "タグ名は必須です"}), 400

    tag_id = build_mod.slugify(name)
    tags = build_mod.load_tags()

    existing = next((t for t in tags if t["id"] == tag_id), None)
    if not existing:
        tags.append({"id": tag_id, "name": name})
        build_mod.save_tags(tags)
        tags = build_mod.load_tags()

    return jsonify({"ok": True, "id": tag_id, "tags": tags})


@app.route("/api/tags/<tag_id>", methods=["DELETE"])
def api_delete_tag(tag_id):
    """タグを削除する。紐づいている記事があればfrontmatterからそのタグを
    取り除いてから、tags.jsonから削除する。"""
    for md_path in ARTICLES_DIR.glob("*.md"):
        article = build_mod.parse_article(md_path)
        if article and tag_id in article["tags"]:
            remaining = [t for t in article["tags"] if t != tag_id]
            raw = md_path.read_text(encoding="utf-8")
            match = build_mod.FRONTMATTER_RE.match(raw)
            body = match.group(2) if match else raw
            write_article(article["id"], article["title"], article["date"], remaining, body.strip())

    tags = [t for t in build_mod.load_tags() if t["id"] != tag_id]
    build_mod.save_tags(tags)

    articles = build_mod.build()
    return jsonify({"ok": True, "articles": articles, "tags": build_mod.load_tags()})


@app.route("/api/git-push", methods=["POST"])
def api_git_push():
    """保存とは独立した明示的な操作。失敗したらそのままエラーを返す。
    upstream未設定（初回push）の場合は自動で --set-upstream を付けてリトライする。"""
    data = request.get_json(force=True) or {}
    message = data.get("message") or "Update blog articles"

    def run_git(args, check=False):
        # Windowsではtext=Trueだけだとロケールの既定エンコーディング（cp932等）が
        # 使われ、gitのUTF-8出力（日本語ファイル名など）でUnicodeDecodeErrorになる。
        # encodingを明示し、万一デコードできないバイトがあってもクラッシュしないようにする。
        return subprocess.run(
            args, cwd=REPO_ROOT, check=check, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )

    try:
        run_git(["git", "add", "articles", "articles.json", "tags.json"], check=True)
        commit = run_git(["git", "commit", "-m", message])
        nothing_to_commit = (
            "nothing to commit" in commit.stdout
            or "no changes added to commit" in commit.stdout
        )
        if commit.returncode != 0 and not nothing_to_commit:
            return jsonify({"ok": False, "error": commit.stdout + commit.stderr}), 500

        push = run_git(["git", "push"])

        if push.returncode != 0 and "no upstream branch" in (push.stderr or ""):
            branch = run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True).stdout.strip()
            push = run_git(["git", "push", "--set-upstream", "origin", branch])

        if push.returncode != 0:
            return jsonify({"ok": False, "error": (push.stdout or "") + (push.stderr or "")}), 500

        return jsonify({"ok": True, "log": push.stdout + push.stderr})
    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": (e.stdout or "") + (e.stderr or "")}), 500
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "gitコマンドが見つかりません"}), 500


def startup_diagnostics():
    print(f"📁 作業フォルダ: {REPO_ROOT.resolve()}")
    articles = build_mod.build()
    missing = [a for a in articles if not (REPO_ROOT / a["file"]).exists()]
    if missing:
        print("⚠️  articles.jsonにあるのに実ファイルが見つからない記事があります:")
        for a in missing:
            print(f"   - {a['title']}  →  {a['file']} が存在しません")
    else:
        print(f"✅ 記事ファイル {len(articles)}件、すべて確認OK")


def open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    startup_diagnostics()
    if "--no-browser" not in sys.argv:
        Timer(1.0, open_browser).start()
    print(f"🌿 aoyagi blog editor: http://127.0.0.1:{PORT}  (Ctrl+Cで終了)")
    app.run(port=PORT, debug=False)
