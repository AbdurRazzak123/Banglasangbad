/**
 * বাংলা সংবাদ — Google Sheet → GitHub fast trigger
 *
 * This script does NOT contain your GitHub token in the repository.
 * Store the token in Apps Script Project Settings → Script Properties:
 *   GITHUB_TOKEN = <your fine-grained GitHub token>
 *
 * Then run installBanglaSangbadTriggers() once and approve permissions.
 */

const GITHUB_OWNER = 'abdurrazzak123';
const GITHUB_REPO = 'Banglasangbad';
const GITHUB_EVENT = 'news_updated';
const SHEET_NAME = 'Bangla News';
const DEBOUNCE_SECONDS = 15;

function installBanglaSangbadTriggers() {
  const ss = SpreadsheetApp.getActive();
  const handlers = new Set(['banglaSangbadGithubDispatch']);

  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (handlers.has(trigger.getHandlerFunction())) {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('banglaSangbadGithubDispatch')
    .forSpreadsheet(ss)
    .onEdit()
    .create();

  ScriptApp.newTrigger('banglaSangbadGithubDispatch')
    .forSpreadsheet(ss)
    .onFormSubmit()
    .create();

  SpreadsheetApp.getUi().alert(
    'Fast GitHub trigger installed. নতুন/পরিবর্তিত নিউজে GitHub Sync দ্রুত শুরু হবে।'
  );
}

function banglaSangbadGithubDispatch(e) {
  const sheet = e && e.range ? e.range.getSheet() : null;
  if (sheet && sheet.getName() !== SHEET_NAME) return;

  // Avoid duplicate dispatches when several cells are edited quickly.
  const props = PropertiesService.getScriptProperties();
  const now = Date.now();
  const last = Number(props.getProperty('LAST_GITHUB_DISPATCH_MS') || 0);
  if (now - last < DEBOUNCE_SECONDS * 1000) return;
  props.setProperty('LAST_GITHUB_DISPATCH_MS', String(now));

  const token = props.getProperty('GITHUB_TOKEN');
  if (!token) {
    throw new Error(
      'GITHUB_TOKEN is missing from Apps Script Project Settings → Script Properties.'
    );
  }

  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`;
  const payload = {
    event_type: GITHUB_EVENT,
    client_payload: {
      source: 'google_sheet',
      sheet: SHEET_NAME,
      changed_at: new Date().toISOString()
    }
  };

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`GitHub repository_dispatch failed: HTTP ${code} ${response.getContentText()}`);
  }
}
