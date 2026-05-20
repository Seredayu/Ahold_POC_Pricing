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

export async function fetchRecommendations(store_id = 'BE01') {
  const session = await ensureSession()
  const op = await session.executeStatement(`
    SELECT item_id, current_price, stock, hours_to_close,
           sales_velocity_7d, discount_pct, recommended_price,
           confidence, manager_required
    FROM   ahold_poc.gold.recommended_price
    WHERE  store_id        = '${store_id.replace(/[^A-Z0-9]/gi, '')}'
      AND  recommended     = true
    ORDER  BY discount_pct DESC
  `)
  const rows = await op.fetchAll()
  await op.close()

  return rows.map(row => ({
    item: {
      item_id:          row.item_id,
      current_price:    Number(row.current_price),
      stock:            Number(row.stock),
      hours_to_close:   Number(row.hours_to_close),
      sales_velocity_7d: Number(row.sales_velocity_7d),
      ...(SKU_NAMES[row.item_id] ?? { name_fr: row.item_id, name_nl: row.item_id }),
    },
    rec: {
      discount_pct:      Number(row.discount_pct),
      recommended_price: Number(row.recommended_price),
      confidence:        Number(row.confidence),
      manager_required:  Boolean(row.manager_required),
    },
  }))
}
