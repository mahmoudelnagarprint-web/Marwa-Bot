// اختبار قراءة فقط عبر node:sqlite — يتأكد أن الكتابة ممنوعة (خط أحمر)
const { DatabaseSync } = require('node:sqlite')
const db = new DatabaseSync('file:G:/ai/Elnagar POS/pos_data.db?mode=ro', { readOnly: true })
const start = db.prepare("SELECT value FROM settings WHERE key='accounting_start_date'").get()
const income = db.prepare("SELECT IFNULL(SUM(amount),0) v FROM transactions WHERE type='Income' AND date>=?").get(String(start.value))
const recv = db.prepare('SELECT IFNULL(SUM(balance),0) t, COUNT(*) c FROM clients WHERE balance>0').get()
console.log('accounting_start_date:', start.value)
console.log('income_window:', income.v)
let blocked = false
try {
  db.exec('CREATE TABLE IF NOT EXISTS __vision_write_probe(x)')
} catch (e) {
  blocked = true
  console.log('write blocked as expected:', e.message)
}
console.log('write actually blocked:', blocked)
db.close()
