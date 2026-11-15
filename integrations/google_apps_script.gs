/**
 * Google Sheet webhook: appends rows sent by the app, and emails you about hot leads.
 *
 * Setup (about 5 minutes):
 * 1. Create a Google Sheet. Open Extensions > Apps Script, delete what's there, paste this file.
 * 2. Change TOKEN below to a long random string (the same value goes in the app's SHEETS_TOKEN).
 *    Change OWNER_EMAIL to the address that should get alerts ('' for none).
 * 3. Save, choose the function "authorize" in the toolbar and click Run. Allow the permissions.
 * 4. Deploy > New deployment > type "Web app". Execute as: Me. Who has access: Anyone. Deploy.
 * 5. Copy the Web app URL (ends in /exec). It goes in the app's SHEETS_WEBHOOK_URL.
 * After editing this script later, use Deploy > Manage deployments > Edit > New version.
 */
const TOKEN = 'change-me-to-a-long-random-string';
const OWNER_EMAIL = '';

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
    const body = JSON.parse(e.postData.contents);
    if (!TOKEN || TOKEN === 'change-me-to-a-long-random-string' || body.token !== TOKEN) {
      return reply({ ok: false, error: 'wrong token' });
    }
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const tabName = String(body.tab || 'Leads').slice(0, 50);
    const sheet = spreadsheet.getSheetByName(tabName) || spreadsheet.insertSheet(tabName);
    if (sheet.getLastRow() === 0 && Array.isArray(body.header)) {
      sheet.appendRow(body.header.map(clean));
      sheet.setFrozenRows(1);
      sheet.getRange(1, 1, 1, body.header.length).setFontWeight('bold');
    }
    const rows = Array.isArray(body.rows) ? body.rows.slice(0, 500) : [];
    rows.forEach(function (row) {
      sheet.appendRow(row.map(clean));
    });
    if (body.notify && OWNER_EMAIL) {
      MailApp.sendEmail(OWNER_EMAIL, String(body.notify.subject || 'New entry').slice(0, 200),
        String(body.notify.body || '').slice(0, 5000));
    }
    return reply({ ok: true, added: rows.length });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/** Text that starts with = + - @ is stored as text, so nothing typed in a chat can become a formula. */
function clean(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' && /^[=+\-@]/.test(value)) return "'" + value;
  return value;
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** Run once from the editor so Google asks for the Sheets and email permissions. */
function authorize() {
  Logger.log('Sheet: ' + SpreadsheetApp.getActiveSpreadsheet().getName());
  Logger.log('Emails left today: ' + MailApp.getRemainingDailyQuota());
}
