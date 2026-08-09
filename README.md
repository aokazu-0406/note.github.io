# 🌿 aoyagi blog

Markdown（frontmatter付き）が唯一の情報源になっているブログシステム。
`articles.json` は手で編集するファイルではなく、`articles/*.md` から
自動生成される「成果物」。

## 構成

```
├── index.html          # ブログ本体（読み取り専用・そのまま公開できる）
├── articles.json        # 自動生成（コミット対象・直接編集しない）
├── tags.json              # タグの一覧（id/表示名）。自動生成・自動同期される
├── articles/
│   └── intro-aoyagi.md  # 記事本体。frontmatterにtitle/date/tagsを書く
│
├── build.py              # articles/*.md → articles.json / tags.json を生成
├── server.py              # ブラウザ編集サーバー（Flask）
└── static/editor.html      # 編集画面（server.pyが配信）
```

## セットアップ（初回のみ）

```bash
pip install -r requirements.txt
```

## 使い方

```bash
python server.py
```

ブラウザで `http://127.0.0.1:5151` が自動で開く。

- 左：記事一覧・新規作成
- 中央：タイトル/日付/タグ/本文の入力フォーム
- 右：リアルタイムプレビュー

**保存する** を押すと：
1. `articles/<id>.md` に frontmatter 付きで書き込み
2. `build.py` が自動で走って `articles.json` を再生成

Gitへの反映は **Gitにpush** ボタンで明示的に行う（保存操作とは分離されているので、
「保存したつもりが勝手にpushされていた」という事故が起きない）。

ブログ本体は `http://127.0.0.1:5151/blog/` で確認できる。実際に公開するときは
`index.html` / `articles.json` / `articles/` の3つをそのままホスティング先に置けばよい。

## タグの仕組み

タグはフリー入力ではなく、`tags.json` に登録された「タグ一覧」から選ぶ方式。

- エディタ左パネルの **タグ管理** で新しいタグを作成できる（記事に紐づける前に単独で作っておける）
- 記事フォームの **タグ** はチェック式のピッカー — タイプミスによる同じ意味のタグの重複が起きない
- タグを削除すると、そのタグを使っている記事からも自動的に外れる（記事自体は消えない）
- `tags.json` はタグの表示名（`name`）を持つので、記事のfrontmatterには半角小文字のID（例: `generative-art`）を書き、
  画面には日本語や大文字混じりの読みやすい名前（例: `生成アート`）を出せる
- ブログ本体（`index.html`）側もタグクリックでその場で絞り込み表示できる（もう一度クリックで解除）

`.md`を直接手で書いた場合など、`tags.json`にまだ無いタグIDを使うと、`build.py`実行時に
`id`と`name`が同じ値で自動登録される（表示名を変えたければ後からエディタで作り直せばよい）。

## トラブルシューティング

### 「記事の読み込みに失敗しました」と出る

`articles.json`が参照しているファイル名（`file`）と、実際に`articles/`にあるファイル名が
一致していない時に出る。原因はだいたいこの2つ：

1. **記事ファイルがGitにpushされていない**（`articles/`だけ追加し忘れているなど）
   → `git status`で未コミットのファイルが無いか確認してpushし直す
2. **違うフォルダのプロジェクトを開いている**（zipを解凍し直して二重にネストしたフォルダが
   できているなど）→ `python server.py`を起動した時に表示される「作業フォルダ」のパスが、
   実際に見ているフォルダと一致しているか確認する

`python server.py`起動時に、`articles.json`が参照しているファイルが実際に存在するか
自動チェックして警告を出すようにしてある。

### 記事のIDに日本語が混ざっている（古いデータ）

以前のバージョンでは記事IDにタイトルの日本語がそのまま使われることがあった
（`aoyagi-designとは.md`など）。今のバージョンではIDは常に英数字のスラッグになる
（日本語のみのタイトルは`post-日付-ランダム文字列`になる）ので、新しく作成・保存し直せば直る。

古い記事を直すには：
1. `articles/`にある該当の`.md`ファイルの中身をコピーしておく
2. エディタで同じ記事を新規作成として保存し直す（内容を貼り付け）
3. 古い（日本語名の）`.md`ファイルを削除する

### `git push`が失敗する

- `fatal: not a git repository` → `git init`していない。READMEの「Gitとの連携」を参照
- `has no upstream branch` → 初回pushだけ手動で`git push --set-upstream origin main`が必要
- `failed to push some refs` → リモート側に無い変更がローカルに無い（逆）ことが多い。
  `git pull origin main --allow-unrelated-histories`してからpush
- `no changes added to commit`とだけ出る → 「Gitにpush」ボタンは記事系ファイル
  （`articles/`, `articles.json`, `tags.json`）しか対象にしていない。`server.py`や
  `static/editor.html`などコードを変更した時はターミナルから手動で`git add/commit/push`する

## 記事の書き方

`articles/` に `.md` ファイルを直接作ってもいい（エディタ経由でなくてもOK）。
frontmatterの書式はこれだけ：

```markdown
---
title: 記事タイトル
date: 2026-08-10
tags: [kotlin, android, design]
---

本文をMarkdownで。
```

書いたら `python build.py` を実行すれば `articles.json` に反映される
（エディタ経由で保存した場合はこのステップは自動）。

## 旧システムからの変更点

- Tkinterデスクトップアプリ（EXEビルド・専用ランチャーが必要）→ ブラウザで動くエディタに変更。配布の手間がなくなった
- `articles.json` を直接書き換えていた → Markdownのfrontmatterから自動生成する方式に変更。記事本体とメタデータの二重管理・同期ズレがなくなった
- 保存のたびに自動でGit push → 明示的なボタン操作に分離
