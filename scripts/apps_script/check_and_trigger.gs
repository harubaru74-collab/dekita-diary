/**
 * できたこと日記 - 即時トリガー用 Google Apps Script
 *
 * やること:
 *   1分おきにGoogle Driveの「できたこと日記」フォルダを確認し、
 *   今日の日付の日記が見つかったら、GitHub Actions(update-diary.yml)を
 *   その場で起動する(workflow_dispatch)。
 *   これにより、GitHub Actions側の毎時0分の定期チェックを待たずに、
 *   日記を書いてから最短1分以内にサイトが更新されるようになる。
 *
 * セットアップ手順は ../../SETUP.md の「ステップ6」を参照。
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
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');

  // 今日すでに起動済みなら何もしない(1日1回だけ起動すればよい)
  const lastTriggered = props.getProperty('lastTriggeredDate');
  if (lastTriggered === today) {
    return;
  }

  // 今日の日付の日記がGoogle Driveにあるか確認
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const files = folder.getFiles();
  let found = false;
  while (files.hasNext()) {
    const name = files.next().getName();
    if (name.indexOf(today) !== -1 &&
        (name.indexOf('のできごと') !== -1 || name.indexOf('できたこと日記') !== -1)) {
      found = true;
      break;
    }
  }

  if (!found) {
    return; // まだ書かれていない。次の1分後にまた確認する
  }

  // GitHub Actionsのワークフローを起動する
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

  // 204 (No Content) = 起動成功。今日はもう起動しない
  if (response.getResponseCode() === 204) {
    props.setProperty('lastTriggeredDate', today);
  }
}
