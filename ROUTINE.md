# 「できたこと日記」成長可視化の運用方法（2026-08-25〜：GitHub Actions自動化）

## 経緯（方式の変遷）

1. 最初はGoogle Drive手動保存＋Claudeの毎時Routineでチェックする方式で作った。
2. 「待機中もトークンを消費するのが心配」というフィードバックを受け、Claudeとの対話の中で直接サイトを更新する方式に変えた（Google Drive不要）。
3. さらに「Cowork環境からGitHub認証ができない」という制約が判明し、**GitHub Actionsによる完全自動化**に切り替えた（2026-08-25）。これにより、Claudeのセッション・トークンを一切使わずに自動更新できるようになった。
4. 「日記を書いた瞬間に近いタイミングで更新してほしい」という要望を受け、**Google Apps Script**（1分おきにGoogle Driveを監視し、新しい日記を見つけたらGitHub Actionsを即時起動する）を追加した（2026-08-25）。これにより、毎時0分を待たず**最短1分以内**に反映されるようになった。

## 今の仕組み

```
はるかちゃんがCoworkでチャッピーと日記をまとめる
   ↓（今まで通り）
Google Drive「できたこと日記」フォルダに保存
   ↓（Google Apps Scriptが1分おきに監視、新しい日記を発見）
GitHub Actionsをその場で起動（workflow_dispatch）
   ↓
scripts/build_diary_page.py が今日の日記を検出
   ↓
diary/YYYY-MM-DD.md に保存 + docs/index.html を再構築
   ↓
git commit & push（差分が無ければ何もしない）
   ↓
GitHub Pages が自動で最新版を配信
```

- **Claudeのトークンは一切消費しない**（GitHub Actions・Google Apps Scriptとも無料枠内で完結。Publicリポジトリなので実行時間は無制限に無料）。
- 日記を書いてからサイトに反映されるまで、**最短1分以内**（Google Apps Scriptによる即時起動、2026-08-25設定）。万一Apps Script側が動かない場合でも、GitHub Actions自体の毎時0分の定期チェックが保険として残っている（最大1時間弱）。
- セットアップ手順（GitHubトークン発行・Apps Scriptの設置・トリガー設定）は [`../SETUP.md`](../SETUP.md) の「ステップ6」を参照。

## セットアップについて

Google CloudでのサービスアカウントAPI設定、GitHubリポジトリへのシークレット登録、GitHub Pagesの有効化は、
はるかちゃん自身のアカウントでの操作が必要なため、Claudeは代行できない。手順は [`../SETUP.md`](../SETUP.md) を参照。

## 公開範囲について（重要）

日記の内容（恋愛・家族・退職相談など）は非常にプライベートだが、GitHub Pagesは**無料プランだとPrivateリポジトリでは使えない**ことが判明したため、**リポジトリごとPublicにし、割り切って公開する方式にした**（2026-08-25、はるかちゃん了承の上で決定）。

- リポジトリ（コード・`diary/`の日記生データを含む）は現在 **Public**。GitHub上で誰でもファイルの中身を読める状態。
- サイト（`docs/`）も、URLを知っていれば誰でも見られる。
- 検索エンジンへの掲載だけは `docs/robots.txt` と `<meta name="robots" content="noindex">` で防いでいる（ただしGitHub上の生ファイル自体の検索避けにはならない）。
- URLを人に教えない・SNS等に貼らないことで、実質的な非公開性を保つ運用にする。

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
