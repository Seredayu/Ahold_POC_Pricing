import { DBSQLClient } from '@databricks/sql'

const SKU_NAMES = {
  'SKU-001': { name_fr: 'Fraises biologiques 500g',        name_nl: 'Biologische aardbeien 500g' },
  'SKU-002': { name_fr: 'Poulet rôti Label Rouge 1.2kg',   name_nl: 'Geroosterde kip Label Rouge 1.2kg' },
  'SKU-003': { name_fr: 'Croissants beurre x6',            name_nl: 'Boter croissants x6' },
  'SKU-004': { name_fr: 'Saumon fumé 200g',                name_nl: 'Gerookte zalm 200g' },
  'SKU-005': { name_fr: 'Pain de campagne 400g',           name_nl: 'Boerenbrood 400g' },
  'SKU-006': { name_fr: 'Fromage de chèvre frais 150g',    name_nl: 'Verse geitenkaas 150g' },
  'SKU-007': { name_fr: 'Tarte aux pommes 400g',           name_nl: 'Appeltaart 400g' },
  'SKU-008': { name_fr: 'Yaourt grec 500g',                name_nl: 'Griekse yoghurt 500g' },
  'SKU-009': { name_fr: 'Pâté de campagne 200g',           name_nl: 'Boerenpaté 200g' },
  'SKU-010': { name_fr: 'Baguette tradition',              name_nl: 'Traditioneel stokbrood' },
  'SKU-011': { name_fr: 'Salade de fruits frais 400g',     name_nl: 'Verse fruitsalade 400g' },
  'SKU-012': { name_fr: 'Charcuterie artisanale 150g',     name_nl: 'Ambachtelijke vleeswaren 150g' },
}

const client = new DBSQLClient()
let _connection = null
let _session = null

async function ensureSession() {
  if (_session) return _session
  _connection = await client.connect({
    host:  process.env.DATABRICKS_HOST,
    path:  process.env.DATABRICKS_HTTP_PATH,
    token: process.env.DATABRICKS_TOKEN,
  })
  _session = await _connection.openSession()
  return _session
}

function toItemRec(row, names) {
  return {
    item: {
      item_id:           row.item_id,
      name_fr:           row.name_fr  ?? names?.name_fr ?? row.item_id,
      name_nl:           row.name_nl  ?? names?.name_nl ?? row.item_id,
      current_price:     Number(row.current_price),
      stock:             Number(row.stock),
      hours_to_close:    Number(row.hours_to_close),
      sales_velocity_7d: Number(row.sales_velocity_7d),
    },
    rec: {
      discount_pct:      Number(row.discount_pct),
      recommended_price: Number(row.recommended_price),
      confidence:        Number(row.confidence),
      manager_required:  Boolean(row.manager_required),
    },
  }
}

export async function fetchRecommendations(store_id = 'BE01') {
  const sid = store_id.replace(/[^A-Z0-9]/gi, '')
  const session = await ensureSession()

  // Prefer today's manual uploads over DLT Gold
  let uploadCount = 0
  try {
    const cntOp = await session.executeStatement(
      `SELECT COUNT(*) AS cnt FROM ahold_poc.gold.manual_upload WHERE store_id = '${sid}' AND upload_date = current_date()`
    )
    const cntRows = await cntOp.fetchAll()
    await cntOp.close()
    uploadCount = Number(cntRows[0]?.cnt ?? 0)
  } catch { /* table not created yet */ }

  if (uploadCount > 0) {
    const op = await session.executeStatement(`
      SELECT item_id, name_fr, name_nl, current_price, stock, hours_to_close,
             sales_velocity_7d, discount_pct, recommended_price, confidence, manager_required
      FROM   ahold_poc.gold.manual_upload
      WHERE  store_id = '${sid}' AND upload_date = current_date()
      ORDER  BY discount_pct DESC
    `)
    const rows = await op.fetchAll()
    await op.close()
    return rows.map(r => toItemRec(r, null))
  }

  const op = await session.executeStatement(`
    SELECT item_id, current_price, stock, hours_to_close,
           sales_velocity_7d, discount_pct, recommended_price,
           confidence, manager_required
    FROM   ahold_poc.gold.recommended_price
    WHERE  store_id    = '${sid}'
      AND  recommended = true
    ORDER  BY discount_pct DESC
  `)
  const rows = await op.fetchAll()
  await op.close()
  return rows.map(r => toItemRec(r, SKU_NAMES[r.item_id]))
}

export async function writeManualUpload(store_id, items) {
  const session = await ensureSession()
  const sid = store_id.replace(/[^A-Z0-9]/gi, '')

  const ddlOp = await session.executeStatement(`
    CREATE TABLE IF NOT EXISTS ahold_poc.gold.manual_upload (
      item_id STRING, store_id STRING, name_fr STRING, name_nl STRING,
      current_price DOUBLE, stock DOUBLE, hours_to_close DOUBLE, sales_velocity_7d DOUBLE,
      expiry_risk DOUBLE, discount_pct DOUBLE, recommended_price DOUBLE,
      confidence DOUBLE, manager_required BOOLEAN, recommended BOOLEAN,
      upload_ts TIMESTAMP, upload_date DATE
    )
  `)
  await ddlOp.close()

  const delOp = await session.executeStatement(
    `DELETE FROM ahold_poc.gold.manual_upload WHERE store_id = '${sid}' AND upload_date = current_date()`
  )
  await delOp.close()

  const esc = s => String(s).replace(/'/g, "''")
  const vals = items.map(r =>
    `('${esc(r.item_id)}','${sid}','${esc(r.name_fr)}','${esc(r.name_nl)}',` +
    `${r.current_price},${r.stock},${r.hours_to_close},${r.sales_velocity_7d},` +
    `${r.expiry_risk},${r.discount_pct},${r.recommended_price},${r.confidence},` +
    `${r.manager_required},${r.recommended},current_timestamp(),current_date())`
  ).join(',')

  const insOp = await session.executeStatement(
    `INSERT INTO ahold_poc.gold.manual_upload VALUES ${vals}`
  )
  await insOp.close()
}
