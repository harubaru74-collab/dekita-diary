# dekita-diary(できたこと日記 成長可視化)

はるかちゃんの「できたこと日記」(Google Drive に保存)を、今日・1週間前・1ヶ月前・1年前の同じ日付で並べて表示し、日々の成長を実感するためのプロジェクト。

## このリポジトリの役割

- `diary/` … Google Drive に書いた日記本文の永続バックアップ(Markdown、原文のまま)
- `archive/shell.html` … 成長可視化ページのデザインの型
- `archive/BUILD.md` … ページの再生成手順・HTML変換ルール
- `ROUTINE.md` … 毎晩22:00 JSTの自動更新ルーティンの仕様

## 公開範囲について

日記の内容が非常にプライベートなため、このリポジトリは Private、成長可視化ページも非公開のClaude Artifactとして運用している(GitHub Pagesは使わない)。詳細は [`ROUTINE.md`](./ROUTINE.md) の「公開・非公開について」を参照。

## 自動更新について

毎晩22:00 JSTに自動実行するルーティンとして運用している。詳細は [`ROUTINE.md`](./ROUTINE.md) を参照。
