# dekita-diary(できたこと日記 成長可視化)

はるかちゃんの「できたこと日記」を、今日・1週間前・1ヶ月前・1年前の同じ日付で並べて表示し、日々の成長を実感するためのプロジェクト。

## 仕組み

1. Claude(Cowork)と対話して日記をまとめ、Google Driveの「できたこと日記」フォルダに保存する(これまで通り)。
2. GitHub Actions(`.github/workflows/update-diary.yml`)が毎時0分に自動チェックし、新しい日記があれば `scripts/build_diary_page.py` がページを再構築してpushする。
3. GitHub Pages(`docs/`)が最新版を配信する。

Claudeのセッション・トークンは自動更新に一切使わない。

## セットアップ

Google CloudサービスアカウントとGitHub側の設定が必要。手順は [`SETUP.md`](./SETUP.md) を参照(はるかちゃん自身のアカウントでの操作が必要なため)。

## このリポジトリの役割

- `diary/` … 日記本文(Markdown、原文のまま)。2026-08-16〜08-24分は初期移行データ
- `docs/` … GitHub Pagesが配信する成長可視化ページ本体
  - `index.html` … 自動生成されるページ本体(手で編集しないこと)
  - `manifest.json` / `sw.js` / `icons/` … PWA化(2026-08-25追加)のための静的ファイル。スクリプトの再生成対象外
- `archive/shell.html` … 成長可視化ページのデザインの型(PWA用のlinkタグ・SW登録スクリプトもここに含む)
- `archive/BUILD.md` … `scripts/build_diary_page.py` が実装している変換ルールの仕様書
- `scripts/build_diary_page.py` … Google Drive読込→HTML生成→保存を行う本体スクリプト
- `.github/workflows/update-diary.yml` … 自動実行するGitHub Actionsワークフロー
- `ROUTINE.md` … 運用方法の詳細
- `SETUP.md` … 初回セットアップ手順(Google Cloud・GitHub側の設定)

## 公開範囲について

日記の内容は非常にプライベートだが、無料でGitHub Pagesを使うにはリポジトリをPublicにする必要があったため、**リポジトリ・サイトともに現在Public**（URLやリポジトリの場所を知っていれば誰でも閲覧可能）。検索エンジンには載らないよう設定済みだが、URLは他人に教えないこと。詳細は [`ROUTINE.md`](./ROUTINE.md) の「公開範囲について」を参照。
