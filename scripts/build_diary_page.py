#!/usr/bin/env python3
"""
できたこと日記 成長可視化ページ ビルドスクリプト

やること:
  1. Google Drive の「できたこと日記」フォルダの中身を最新化する
     (diary/*.md。sync_all_diary_files()参照)。
  2. 同じフォルダにある月間レポート(タイトルに「月間レポート」を含む
     ファイル)も最新化する(monthly/*.md。sync_monthly_reports()参照)。
  3. diary/*.md・monthly/*.md を全部読み込み、archive/shell.html を土台に
     docs/index.html (GitHub Pagesが配信するページ)を再構築する。

前提:
  - 環境変数 GDRIVE_SA_KEY_JSON に、Google Cloud のサービスアカウントの
    JSON鍵の中身(そのままの文字列)が入っていること。
  - サービスアカウントが、対象のGoogle Driveフォルダに「閲覧者」として
    共有されていること。
  - セットアップ手順は SETUP.md を参照。
"""
import datetime
import html
import io
import json
import os
import re
import sys

FOLDER_ID = "1dD_DwKfXys_sycnoS9H9FbOWu8yhqr4P"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIARY_DIR = os.path.join(REPO_ROOT, "diary")
SHELL_PATH = os.path.join(REPO_ROOT, "archive", "shell.html")
OUT_PATH = os.path.join(REPO_ROOT, "docs", "index.html")

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

def get_drive_service():
    # 遅延importにしておく(google-api-python-client等はGitHub Actions実行時にだけ必要で、
    # HTML生成ロジックだけをローカルでテストする際にはインストール不要にするため)。
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_json = os.environ.get("GDRIVE_SA_KEY_JSON")
    if not key_json:
        print("GDRIVE_SA_KEY_JSON が設定されていません。SETUP.md を参照してください。", file=sys.stderr)
        sys.exit(1)
    info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def list_diary_files(service):
    """フォルダ内の日記ファイルを全部リストする(ページングに対応)。
    タイトルに日付＋「のできごと」/「できたこと日記」を含むものだけを対象にする
    (同フォルダに無関係なファイルが混ざっていることがあるため)。"""
    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    result = {}
    for f in files:
        name = f["name"]
        if not ("のできごと" in name or "できたこと日記" in name):
            continue
        m = DATE_IN_NAME.search(name)
        if not m:
            continue
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        result[d] = f
    return result


def download_text(service, file):
    from googleapiclient.http import MediaIoBaseDownload

    if file["mimeType"] == "application/vnd.google-apps.document":
        data = service.files().export(fileId=file["id"], mimeType="text/plain").execute()
        return data.decode("utf-8") if isinstance(data, bytes) else data
    request = service.files().get_media(fileId=file["id"])
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# テキスト整形
# ---------------------------------------------------------------------------

def unescape_md(text):
    r"""Google Drive の text/plain が返す `\#` `\*\*` `\-` 等のエスケープを戻す。"""
    return re.sub(r"\\([#*\-\[\]()>.!])", r"\1", text)


def clean_mojibake(text):
    """絵文字が `ð` 等の文字化けで来た場合、意味のない断片を除去する。"""
    return re.sub(r"ð[\x80-\xbf\xa0-\xff]{0,3}", "", text)


def normalize_text(text):
    return clean_mojibake(unescape_md(text)).strip() + "\n"


HEADER_MAP = {
    "genbun": ("原文",),
    "dekigoto": ("今日のできごと",),
    "dekita": ("できたこと",),
    "summary": ("要約",),
    "chappy": ("チャッピー",),
    # 2026-08-25追加: メンタルコンディショニング機能(任意セクション)。
    # しんどい・悩みがある日だけ、Cowork側の判断でこの3セクションを追加してもらう。
    # 元気な日は書かなくてよい(セクションが無ければ何も表示されない)。
    "mental": ("メンタル状態",),
    "overcome_log": ("乗り越えログ",),
    "takeshi_message": ("毅さんからのメッセージ", "毅さんメッセージ"),
}


def parse_diary(text):
    """`## 見出し` ごとにセクションへ分割する(実処理はsplit_sections()を参照)。"""
    return split_sections(text, HEADER_MAP)


def list_items(text):
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*・]\s*", "", line)
        # 2026-08-25: 日記作成側で「[stated]」等のデバッグ用タグが本文に
        # 紛れ込んで保存されることがあったため、表示直前で防御的に除去する
        # (見た目が「文が途中で切れている」ように誤解されてしまうため)。
        line = re.sub(r"^\[[a-zA-Z_-]+\]\s*", "", line)
        if line:
            items.append(line)
    return items


def esc(s):
    return html.escape(s, quote=False)


def md_bold(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(s))


TERMINAL_PUNCT = "。！？!?"


def to_prose(items):
    """箇条書きの項目群を、読みやすい1つの文章(段落)に変換する。
    「できたこと」欄(箇条書きのまま)と見た目が重複しないよう、
    「今日のできごと」欄はこちらを通して文章化して表示する。
    項目が既に「！」「？」等で終わっている場合はそのまま活かし、
    句点が無い場合だけ「。」を補う(「！。」のような二重句読点を避ける)。"""
    parts = []
    for it in items:
        it = it.strip()
        if not it:
            continue
        if it[-1] not in TERMINAL_PUNCT:
            it += "。"
        parts.append(it)
    return "".join(parts)


# ---------------------------------------------------------------------------
# 日付ユーティリティ
# ---------------------------------------------------------------------------

def date_jp(d):
    return f"{d.year}年{d.month}月{d.day}日（{WEEKDAY_JP[d.weekday()]}）"


def diary_path(d):
    return os.path.join(DIARY_DIR, f"{d.isoformat()}.md")


# ---------------------------------------------------------------------------
# 同期状態の記録(2026-09-05追加)
#
# 「diary/にその日付のファイルが既にあるかどうか」だけでは、Google Drive側で
# 後から内容を書き直したり、間違った日付のファイル名を正しい日付に直したり
# した変更を検知できない(前回の同期時点の状態と比べようがないため)。
# そこで、前回同期した各日付のDriveファイルID・更新日時を
# diary/.sync_manifest.json に記録しておき、次回はそれと比較して
# 「変わっていたら再取得」「Drive側から消えていたらローカルも削除」を
# 判断できるようにする。
# ---------------------------------------------------------------------------

MANIFEST_PATH = os.path.join(DIARY_DIR, ".sync_manifest.json")


def load_manifest(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_manifest(path, manifest):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------------------
# HTML生成
# ---------------------------------------------------------------------------

def render_empty_card(badge, today=False):
    if today:
        emoji, msg = "📝", "今日の分はまだ届いていないよ<br />書いたら次回の自動更新で反映されるよ"
        cls = "card empty today"
    else:
        emoji, msg = "🌱", "まだ記録がないよ<br />これからの積み重ねが楽しみだね"
        cls = "card empty"
    return f'''    <div class="{cls}">
      <span class="badge">{badge}</span>
      <div class="emoji">{emoji}</div>
      <p>{msg}</p>
    </div>'''


def render_card_body(d, sections):
    """カードの中身(日付・できたこと・詳細)だけを作る。外側の
    <div class="card ...">と<span class="badge">は含まない
    (badge/kind_classはその時々の役割(今日/1週間前/...)で変わるため、
    呼び出し側で被せる。カレンダー機能用に、日付を選ばずJSでも
    このHTMLをそのまま再利用できるようにするための分離)。"""
    dekita_items = list_items(sections.get("dekita", ""))
    dekita_html = "\n".join(f"    <li>{md_bold(x)}</li>" for x in dekita_items)

    blocks = [f'''      <div class="date">{date_jp(d)}</div>
      <ul class="dekita">
{dekita_html}
      </ul>''']

    dekigoto_items = list_items(sections.get("dekigoto", ""))
    if dekigoto_items:
        body = md_bold(to_prose(dekigoto_items))
        blocks.append(f'''      <details>
        <summary>今日のできごとを見る</summary>
        <div class="body-text">{body}</div>
      </details>''')

    if sections.get("chappy"):
        blocks.append(f'''      <details>
        <summary>チャッピーからのコメントを見る</summary>
        <div class="chappy">{esc(sections["chappy"])}</div>
      </details>''')

    if sections.get("summary"):
        blocks.append(f'      <p class="summary-line">{esc(sections["summary"])}</p>')

    return "\n".join(blocks)


def render_card(kind_class, badge, d, sections):
    body = render_card_body(d, sections)
    return f'''    <div class="card {kind_class}">
      <span class="badge">{badge}</span>
{body}
    </div>'''


def render_message_card(sections):
    """メンタルコンディショニング機能: しんどい・悩みがある日だけ、Cowork側の
    判断で書かれる任意セクション(メンタル状態/乗り越えログ/毅さんからの
    メッセージ)からカードを作る。「毅さんからのメッセージ」が無い日は
    空文字を返す(=何も表示しない。元気な日はこのカード自体が出ない)。"""
    message = sections.get("takeshi_message", "").strip()
    if not message:
        return ""

    energy_line = ""
    mental = sections.get("mental", "")
    m = re.search(r"エネルギー[:：]\s*(.+)", mental)
    if m:
        energy_line = f'<div class="message-energy">今日のエネルギー：{esc(m.group(1).strip())}</div>'

    overcome_html = ""
    if sections.get("overcome_log"):
        overcome_html = f'''
      <details>
        <summary>前にも乗り越えた日があるよ</summary>
        <div class="body-text">{esc(sections["overcome_log"])}</div>
      </details>'''

    return f'''  <div class="message-card">
    <span class="badge">🫂 今日のひとこと</span>
    {energy_line}
    <p class="message-text">{esc(message)}</p>{overcome_html}
  </div>
'''


def make_headline(sections):
    items = list_items(sections.get("dekita", "")) or list_items(sections.get("dekigoto", ""))
    if not items:
        return "今日の記録"
    headline = re.sub(r"\*\*(.+?)\*\*", r"\1", items[0])
    headline = re.sub(r"[→:：].*$", "", headline).strip()
    if len(headline) > 26:
        headline = headline[:26] + "…"
    return headline


def render_entry(d, sections, open_=False):
    dekigoto_items = list_items(sections.get("dekigoto", ""))
    dekita_items = list_items(sections.get("dekita", ""))
    headline = make_headline(sections)
    badge = f"{d.month}/{d.day}"

    parts = []
    if dekigoto_items:
        parts.append(f"    <h4>今日のできごと</h4>\n    <p>{md_bold(to_prose(dekigoto_items))}</p>")
    if dekita_items:
        lis = "\n".join(f"      <li>{md_bold(x)}</li>" for x in dekita_items)
        parts.append(f"    <h4>できたこと</h4>\n    <ul>\n{lis}\n    </ul>")
    if sections.get("summary"):
        parts.append(f'    <h4>要約</h4>\n    <p>{esc(sections["summary"])}</p>')
    if sections.get("chappy"):
        parts.append(
            "    <details>\n"
            "      <summary>チャッピーからのコメントを見る</summary>\n"
            f'      <div class="chappy">{esc(sections["chappy"])}</div>\n'
            "    </details>"
        )
    if sections.get("takeshi_message"):
        parts.append(
            "    <details>\n"
            "      <summary>この日のひとことを見る</summary>\n"
            f'      <div class="chappy">{esc(sections["takeshi_message"])}</div>\n'
            "    </details>"
        )
    body = "\n".join(parts)

    open_attr = " open" if open_ else ""
    return f'''<details class="entry" id="entry-{d.isoformat()}"{open_attr}>
  <summary>
    <span class="entry-badge">{badge}</span>
    <span class="entry-headline">{esc(headline)}</span>
    <span class="entry-toggle" aria-hidden="true">▾</span>
  </summary>
  <div class="entry-body">
{body}
  </div>
</details>'''


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def load_existing(d):
    path = diary_path(d)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return parse_diary(f.read())


def save_diary_file(d, raw_text, title_hint):
    """diary/YYYY-MM-DD.md として保存する(常に上書き)。
    「既にあればスキップ」の判断は呼び出し側(sync_all_diary_files)が
    .sync_manifest.json と比べて行うので、ここでは常に書き込む
    (2026-09-05、内容の修正や日付の訂正が反映されない不具合を修正)。"""
    os.makedirs(DIARY_DIR, exist_ok=True)
    path = diary_path(d)
    header = f"# {d.isoformat()} のできごと\n\n"
    body = normalize_text(raw_text)
    # 既にトップの`#`見出しが入っている場合は二重に付けない
    if body.lstrip().startswith("#"):
        content = body
    else:
        content = header + body
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def sync_all_diary_files(service):
    """Google Driveの日記フォルダ全体をスキャンし、diary/を最新化する。

    - 新しい日付のファイルは保存する。「今日」だけでなく、書き忘れて
      後からまとめて投稿した過去日の日記も、これで確実に拾われる
      (2026-08-27、「昨日の分を書いたのにサイトに反映されない」という
      フィードバックを受けて、今日/7日前/30日前/365日前の4点だけを
      見に行く方式から、フォルダ全体の同期に変更した)。
    - 既にdiary/にある日付でも、前回同期時からDrive側のファイルID・
      更新日時が変わっていれば再取得して上書きする(2026-09-05追加。
      以前は「diary/に既にあればスキップ」だったため、後から内容を
      修正したり、間違った日付のファイル名を書き直したりしても
      サイトに反映されないという不具合があった)。
    - 前回同期時にはあったのに、今回のフォルダの中に同じ日付のファイルが
      見当たらなくなった場合(=ファイル名の日付を書き直して別の日付に
      なった、またはファイルが削除された)は、ローカルのdiary/ファイルも
      削除する。ただし対象は前回このスクリプトが同期して記録した日付
      (.sync_manifest.json にある日付)だけで、Driveのタイトルと1対1で
      対応しない初期移行データには絶対に触れない。

    戻り値: (更新した日付のリスト, 削除した日付のリスト)。
    """
    drive_files = list_diary_files(service)
    manifest = load_manifest(MANIFEST_PATH)
    new_manifest = {}
    updated = []

    for d, file in drive_files.items():
        key = d.isoformat()
        mtime = file.get("modifiedTime", "")
        new_manifest[key] = {"id": file["id"], "modifiedTime": mtime}
        prev = manifest.get(key)
        needs_sync = (
            not os.path.exists(diary_path(d))
            or prev is None
            or prev.get("id") != file["id"]
            or prev.get("modifiedTime") != mtime
        )
        if needs_sync:
            raw = download_text(service, file)
            save_diary_file(d, raw, file["name"])
            updated.append(d)

    removed = []
    for key in manifest:
        if key in new_manifest:
            continue
        try:
            d = datetime.date.fromisoformat(key)
        except ValueError:
            continue
        path = diary_path(d)
        if os.path.exists(path):
            os.remove(path)
            removed.append(d)

    save_manifest(MANIFEST_PATH, new_manifest)
    return updated, removed


# ---------------------------------------------------------------------------
# 月間レポート(2026-09-06追加)
#
# 「今月の成長ハイライト」「価値観・軸」「エピソードの原石」「チャッピーからの
# 月間総括メッセージ」をまとめたレポート。日々の日記と違い、月末などの
# 節目にはるかちゃんがCowork(Claude)へ依頼して生成してもらい、Google Drive
# の同じフォルダにタイトル「YYYY-MM 月間レポート」で保存する運用にする。
#
# なぜGitHub Actions側でLLM解析を自動実行しないか:
#   毎日の自動更新パイプラインはGoogle Drive→静的サイト生成だけで完結して
#   おり、Claude/LLM APIのトークンを一切消費しない設計になっている
#   (README「公開範囲について」参照)。GAS等から毎月LLM APIを呼ぶ設計も
#   可能だが、新たなAPIキーの管理・費用が発生するうえ、既存の「Coworkと
#   話して日記を書く」運用ともズレる。そのため月間レポートも「Coworkと
#   話して生成→Google Driveに保存」という日々の日記と同じ運用に乗せ、
#   このスクリプトは生成済みレポートを拾って表示するだけにしている。
# ---------------------------------------------------------------------------

MONTHLY_DIR = os.path.join(REPO_ROOT, "monthly")
MONTHLY_MANIFEST_PATH = os.path.join(MONTHLY_DIR, ".sync_manifest.json")
MONTH_IN_NAME = re.compile(r"(\d{4})-(\d{2})")

MONTHLY_HEADER_MAP = {
    "highlights": ("成長ハイライト",),
    "values": ("価値観", "軸"),
    "episodes": ("エピソード",),
    "chappy_summary": ("チャッピーからの", "総括"),
}


def monthly_path(month_str):
    return os.path.join(MONTHLY_DIR, f"{month_str}.md")


def list_monthly_reports(service):
    """フォルダ内の月間レポートファイルを全部リストする。タイトルに
    「月間レポート」または「月次レポート」を含むものだけを対象にする
    (日々の日記の判定条件「のできごと」「できたこと日記」とは重ならない
    ので、同じフォルダに混在していても取り違えない)。"""
    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    result = {}
    for f in files:
        name = f["name"]
        if not ("月間レポート" in name or "月次レポート" in name):
            continue
        m = MONTH_IN_NAME.search(name)
        if not m:
            continue
        result[f"{m.group(1)}-{m.group(2)}"] = f
    return result


def sync_monthly_reports(service):
    """月間レポートを同期する。考え方はsync_all_diary_files()と同じ
    (前回同期時の状態と比較して、変わっていれば再取得、Drive側から
    見当たらなくなっていれば削除)。
    戻り値: (更新した月のリスト, 削除した月のリスト)。"""
    drive_files = list_monthly_reports(service)
    manifest = load_manifest(MONTHLY_MANIFEST_PATH)
    new_manifest = {}
    updated = []

    for month_str, file in drive_files.items():
        mtime = file.get("modifiedTime", "")
        new_manifest[month_str] = {"id": file["id"], "modifiedTime": mtime}
        prev = manifest.get(month_str)
        needs_sync = (
            not os.path.exists(monthly_path(month_str))
            or prev is None
            or prev.get("id") != file["id"]
            or prev.get("modifiedTime") != mtime
        )
        if needs_sync:
            raw = download_text(service, file)
            os.makedirs(MONTHLY_DIR, exist_ok=True)
            with open(monthly_path(month_str), "w", encoding="utf-8") as out:
                out.write(normalize_text(raw))
            updated.append(month_str)

    removed = []
    for month_str in manifest:
        if month_str in new_manifest:
            continue
        path = monthly_path(month_str)
        if os.path.exists(path):
            os.remove(path)
            removed.append(month_str)

    save_manifest(MONTHLY_MANIFEST_PATH, new_manifest)
    return updated, removed


def split_sections(text, header_map):
    """`## 見出し`(または`# 見出し`)ごとにテキストを分割し、header_mapに
    書かれたキーワードにマッチする見出しの中身をセクションとして拾う。
    parse_diary()・parse_monthly_report()の共通処理。"""
    body = "\n" + text
    parts = re.split(r"\n#{1,2}\s+", body)
    sections = {}
    for part in parts[1:]:
        lines = part.split("\n", 1)
        header = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        for key, needles in header_map.items():
            if any(n in header for n in needles):
                sections[key] = content
                break
    return sections


def parse_monthly_report(text):
    """月間レポートMarkdownを、タイトル行(`# 見出し`)と各セクションに分ける。"""
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""
    sections = split_sections(text, MONTHLY_HEADER_MAP)
    return title, sections


def render_monthly_report_body(title, sections):
    """月間レポートカードの中身HTMLを作る。render_card_body()と同じ考え方で、
    外側の<div class="card ...">は含まない(JS側でも使い回すため)。"""
    blocks = [f'      <div class="monthly-title">{esc(title)}</div>'] if title else []

    highlight_items = list_items(sections.get("highlights", ""))
    if highlight_items:
        lis = "\n".join(f"        <li>{md_bold(x)}</li>" for x in highlight_items)
        blocks.append(f'''      <div class="monthly-section">
        <h4>🌟 今月の成長ハイライト</h4>
        <ul>
{lis}
        </ul>
      </div>''')

    value_items = list_items(sections.get("values", ""))
    if value_items:
        lis = "\n".join(f"        <li>{md_bold(x)}</li>" for x in value_items)
        blocks.append(f'''      <div class="monthly-section">
        <h4>💎 大切にしている価値観・軸</h4>
        <ul>
{lis}
        </ul>
      </div>''')

    episode_lines = [l for l in sections.get("episodes", "").split("\n") if l.strip()]
    if episode_lines:
        paras = "\n".join(f"        <p>{md_bold(l.strip())}</p>" for l in episode_lines)
        blocks.append(f'''      <div class="monthly-section">
        <h4>💼 エピソードの原石</h4>
{paras}
      </div>''')

    chappy_paras = [p.strip() for p in re.split(r"\n\s*\n", sections.get("chappy_summary", "")) if p.strip()]
    if chappy_paras:
        paras = "\n".join(f"        <p>{md_bold(p)}</p>" for p in chappy_paras)
        blocks.append(f'''      <div class="monthly-section chappy">
        <h4>🔥 チャッピーからの月間総括メッセージ</h4>
{paras}
      </div>''')

    return "\n".join(blocks)


def build_page(anchor=None):
    """anchor: 「今日」として扱う日付(省略時は実際の今日の日付)。
    diary/ に無い日はカードが空表示になる(実際にその日の日記が無いことを正しく示す)。"""
    all_days = []
    if os.path.isdir(DIARY_DIR):
        for name in os.listdir(DIARY_DIR):
            if name.endswith(".md"):
                try:
                    d = datetime.date.fromisoformat(name[:-3])
                    all_days.append(d)
                except ValueError:
                    continue
    all_days.sort(reverse=True)

    if not all_days:
        print("diary/ にファイルが無いのでページ生成をスキップします。")
        return

    today = anchor or datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    year_ago = today - datetime.timedelta(days=365)

    def card_for(kind_class, badge, d, today_flag=False):
        sections = load_existing(d)
        if sections is None:
            return render_empty_card(badge, today=today_flag)
        return render_card(kind_class, badge, d, sections)

    today_card = card_for("today", "今日", today, today_flag=True)
    week_card = card_for("week", "1週間前", week_ago)
    month_card = card_for("month", "1ヶ月前", month_ago)
    year_card = card_for("year", "1年前", year_ago)

    today_sections = load_existing(today) or {}
    message_card = render_message_card(today_sections)

    entries_html = []
    for i, d in enumerate(all_days):
        sections = load_existing(d)
        if sections is None:
            continue
        entries_html.append(render_entry(d, sections, open_=(i == 0)))

    # カレンダー機能(2026-08-27追加)用: 全日記のカード本体をJSONで埋め込み、
    # クリック側で「選んだ日を起点に1週間前/1ヶ月前/1年前」を組み替えられる
    # ようにする(Pythonのrender_card_body()をそのまま使い回すので、
    # 表示ロジックの二重管理にならない)。
    calendar_data = {d.isoformat(): render_card_body(d, load_existing(d)) for d in all_days}
    calendar_json = json.dumps(calendar_data, ensure_ascii=False).replace("</script>", "<\\/script>")

    # 月間レポート機能(2026-09-06追加)用: monthly/*.md を全部読み込み、
    # 月ごとのカード本体HTMLをJSONで埋め込む(1件も無ければ空オブジェクト)。
    monthly_reports = {}
    if os.path.isdir(MONTHLY_DIR):
        for name in sorted(os.listdir(MONTHLY_DIR)):
            if not name.endswith(".md"):
                continue
            month_str = name[:-3]
            if not re.fullmatch(r"\d{4}-\d{2}", month_str):
                continue
            with open(os.path.join(MONTHLY_DIR, name), encoding="utf-8") as f:
                title, sections = parse_monthly_report(f.read())
            monthly_reports[month_str] = render_monthly_report_body(title, sections)
    monthly_report_json = json.dumps(monthly_reports, ensure_ascii=False).replace("</script>", "<\\/script>")

    shell = open(SHELL_PATH, encoding="utf-8").read()
    title_start = shell.find("<title>")
    out = shell[title_start:]
    out = out.replace("{{TODAY_DATE_JP}}", date_jp(today))
    out = out.replace("{{TODAY_DATE_ISO}}", today.isoformat())
    out = out.replace("{{FIRST_DATE_ISO}}", all_days[-1].isoformat())
    out = out.replace("{{DIARY_CALENDAR_JSON}}", calendar_json)
    out = out.replace("{{MONTHLY_REPORT_JSON}}", monthly_report_json)
    out = out.replace("{{DIARY_COUNT}}", str(len(all_days)))
    out = out.replace("{{FIRST_DATE_JP}}", date_jp(all_days[-1]))
    out = out.replace("  <!-- MESSAGE_CARD -->\n", message_card)
    out = out.replace("    <!-- TODAY_CARD -->", today_card)
    out = out.replace("    <!-- WEEK_CARD -->", week_card)
    out = out.replace("    <!-- MONTH_CARD -->", month_card)
    out = out.replace("    <!-- YEAR_CARD -->", year_card)
    out = out.replace("  <!-- ARCHIVE_ENTRIES -->", "\n".join(entries_html))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {OUT_PATH} ({len(out)} bytes), {len(all_days)} diary day(s)")


def main():
    service = get_drive_service()
    today = datetime.date.today()

    updated_dates, removed_dates = sync_all_diary_files(service)
    if updated_dates:
        print(f"更新: {', '.join(d.isoformat() for d in sorted(updated_dates))}")
    if removed_dates:
        print(f"削除(Drive側で日付訂正/削除): {', '.join(d.isoformat() for d in sorted(removed_dates))}")

    if not os.path.exists(diary_path(today)) and today not in updated_dates:
        print(f"{today.isoformat()} の日記はまだ見つかりません。")

    updated_months, removed_months = sync_monthly_reports(service)
    if updated_months:
        print(f"月間レポート更新: {', '.join(sorted(updated_months))}")
    if removed_months:
        print(f"月間レポート削除(Drive側で見当たらず): {', '.join(sorted(removed_months))}")

    # 新しい日記が1件も無い場合でも、日付の表示を最新に保つため
    # (日付をまたいだ後の最初の実行で「今日」ラベルを更新する目的)、
    # ページの再構築は毎回行う。
    build_page()


if __name__ == "__main__":
    main()
