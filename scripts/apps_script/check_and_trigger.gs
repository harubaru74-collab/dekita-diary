/**
 * できたこと日記 - 即時トリガー用 Google Apps Script
 *
 * やること:
 *   1分おきにGoogle Driveの「できたこと日記」フォルダの中身をチェックし、
 *   前回チェック時から何か変化があれば(新しいファイル、内容の修正、
 *   ファイル名=日付の訂正、削除など)、GitHub Actions(update-diary.yml)を
 *   その場で起動する(workflow_dispatch)。
 *   これにより、GitHub Actions側の毎時0分の定期チェックを待たずに、
 *   最短1分以内にサイトが更新されるようになる。
 *
 *   2026-09-05更新: 以前は「今日の日付のファイルが見つかったら、1日1回だけ
 *   起動する」という判定だったため、さかのぼって書いた過去日の日記(後追い
 *   投稿)や、間違った日付をあとから訂正した場合は、この即時トリガーの
 *   対象外になり、GitHub Actions側の毎時チェックが回ってくるまで
 *   (最大で1時間程度、場合によってはそれ以上)反映が遅れていた。
 *   フォルダ全体の「状態のハッシュ値」を比較する方式に変更し、今日の分に
 *   限らずどんな変化でも即座に拾えるようにした。
 *
 * セットアップ手順は ../../SETUP.md の「ステップ6」を参照。
 * 既にステップ6を設定済みの場合は、Apps Scriptエディタでこのファイルの
 * 中身を丸ごと上書きして保存するだけでよい(トリガーやScript Propertiesの
 * 再設定は不要)。
 *
 * 事前に必要なもの(Script Properties、コード中に直接書かない):
 *   - GITHUB_TOKEN … dekita-diaryリポジトリのActionsに書き込み権限を持つ
 *                    GitHub Personal Access Token(fine-grained)
 *
 * トリガー設定:
 *   Apps Scriptエディタの「トリガー」から、この checkAndTrigger 関数を
 *   時間主導・1分おきに実行するよう設定する。
 */

const FOLDER_ID = '1dD_DwKfXys_sycnoS9H9FbOWu8yhqr4P';
const GITHUB_OWNER = 'harubaru74-collab';
const GITHUB_REPO = 'dekita-diary';
const WORKFLOW_FILE = 'update-diary.yml';

function checkAndTrigger() {
  const props = PropertiesService.getScriptProperties();

  // フォルダ内の対象ファイル(id・名前・更新日時)を集めて、
  // 「今のフォルダの状態」を表す1本の文字列にまとめる。
  // 日付は見ず、対象ファイルかどうかだけで拾う(バックデートの日記も
  // 日付訂正のリネームも取りこぼさないため)。
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const files = folder.getFiles();
  const entries = [];
  while (files.hasNext()) {
    const f = files.next();
    const name = f.getName();
    if (name.indexOf('のできごと') !== -1 || name.indexOf('できたこと日記') !== -1) {
      entries.push(f.getId() + '|' + name + '|' + f.getLastUpdated().getTime());
    }
  }
  entries.sort();
  const snapshot = entries.join('\n');

  // フォルダ全体の状態をハッシュ値1本に圧縮して保存する
  // (ファイル数がどれだけ増えてもScript Propertiesの容量を圧迫しないため)。
  const digestBytes = Utilities.computeDigest(
      Utilities.DigestAlgorithm.MD5, snapshot, Utilities.Charset.UTF_8);
  const digest = digestBytes.map(function (b) {
    return (b < 0 ? b + 256 : b).toString(16).padStart(2, '0');
  }).join('');

  const prevDigest = props.getProperty('lastSnapshotHash');
  if (prevDigest === digest) {
    return; // 前回チェック時から変化なし
  }

  const token = props.getProperty('GITHUB_TOKEN');
  if (!token) {
    Logger.log('GITHUB_TOKEN が Script Properties に設定されていません。');
    return;
  }

  const url = 'https://api.github.com/repos/' + GITHUB_OWNER + '/' + GITHUB_REPO +
      '/actions/workflows/' + WORKFLOW_FILE + '/dispatches';

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
    },
    payload: JSON.stringify({ ref: 'main' }),
    muteHttpExceptions: true,
  });

  Logger.log('GitHub response: ' + response.getResponseCode() + ' ' + response.getContentText());

  // 204 (No Content) = 起動成功。今回の状態を記録しておく
  if (response.getResponseCode() === 204) {
    props.setProperty('lastSnapshotHash', digest);
  }
}
