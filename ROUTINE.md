# 「できたこと日記」成長可視化の運用方法（2026-08-25〜：GitHub Actions自動化）

## 経緯（方式の変遷）

1. 最初はGoogle Drive手動保存＋Claudeの毎時Routineでチェックする方式で作った。
2. 「待機中もトークンを消費するのが心配」というフィードバックを受け、Claudeとの対話の中で直接サイトを更新する方式に変えた（Google Drive不要）。
3. さらに「Cowork環境からGitHub認証ができない」という制約が判明し、**GitHub Actionsによる完全自動化**に切り替えた（2026-08-25）。これにより、Claudeのセッション・トークンを一切使わずに自動更新できるようになった。

## 今の仕組み

```
はるかちゃんがCoworkでチャッピーと日記をまとめる
   ↓（今まで通り）
Google Drive「できたこと日記」フォルダに保存
   ↓（GitHub Actionsが毎時0分に自動チェック）
scripts/build_diary_page.py が今日の日記を検出
   ↓
diary/YYYY-MM-DD.md に保存 + docs/index.html を再構築
   ↓
git commit & push（差分が無ければ何もしない）
   ↓
GitHub Pages が自動で最新版を配信
```

- **Claudeのトークンは一切消費しない**（GitHub Actionsの無料枠内で完結。private repoでも毎月2,000分まで無料）。
- 日記を書いてからサイトに反映されるまで、最大1時間弱のタイムラグがある（GitHub Actionsの実用上の最短間隔が1時間のため）。すぐ見たい時は SETUP.md の「手動テスト実行」と同じ手順で即時実行できる。

## セットアップについて

Google CloudでのサービスアカウントAPI設定、GitHubリポジトリへのシークレット登録、GitHub Pagesの有効化は、
はるかちゃん自身のアカウントでの操作が必要なため、Claudeは代行できない。手順は [`../SETUP.md`](../SETUP.md) を参照。

## 公開範囲について（重要）

日記の内容（恋愛・家族・退職相談など）は非常にプライベートだが、GitHub Actionsのスクリプトからは
Claude Artifactを公開できない（Artifact公開はClaudeセッション専用の機能のため）ので、
**GitHub Pagesで公開する方式に切り替えた**（2026-08-25、はるかちゃん了承の上で決定：「割り切って公開にする」）。

- GitHub PagesのURLは、知っていれば誰でも見られる（完全な非公開ではない）。
- 検索エンジンへの掲載だけは `docs/robots.txt` と `<meta name="robots" content="noindex">` で防いでいる。
- URLを人に教えない・SNS等に貼らないことで、実質的な非公開性を保つ運用にする。
- GitHubリポジトリ自体は **Private** のまま維持する（コード・過去の日記データそのものは非公開）。

## チャッピーコメントの扱いについて（重要）

成長可視化ページでは、チャッピーからのコメントを省略してはいけない。**メモを別途見に行かなくても、
サイト上でクリック（`<details>`の展開）すれば全文が読めることが必須要件**（2026-08-25、フィードバックで修正済み）。
`scripts/build_diary_page.py` はこれを満たすように実装されている。

## データソースについて

- 保存場所：Google Drive「できたこと日記」フォルダ
- フォルダID：`1dD_DwKfXys_sycnoS9H9FbOWu8yhqr4P`
- ファイル形式：`YYYY-MM-DD のできごと`（text/plain）。表記ゆれ（`YYYY-MM-DD できたこと日記`等）にも対応済み。
- 同フォルダには日記以外のファイルが混ざることがあるため、日付＋キーワードの両方でタイトルを判定する。

## 運用上の注意

- ワークフロー: `.github/workflows/update-diary.yml`（毎時0分 + 手動実行`workflow_dispatch`）
- スクリプト: `scripts/build_diary_page.py`
- 参考実装：`roumu-news` リポジトリの `archive/BUILD.md`（Markdown→HTML変換の考え方は近い）。ただし労務ニュースは公開ポートフォリオ用、こちらはプライベートな個人用なので、公開範囲の扱いは明確に区別すること。
