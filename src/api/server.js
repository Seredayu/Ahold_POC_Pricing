import express from 'express'
import cors from 'cors'

const app = express()
app.use(cors())
app.use(express.json())

const PORT = process.env.PORT || 3001

// Phase 2B: set BTP_ENABLED=true to route through SAP BTP Cloud Connector.
// Requires all BTP_* env vars (see btp-client.js).
// Default false = Phase 2A mock behaviour preserved.
const BTP_ENABLED        = process.env.BTP_ENABLED === 'true'
const DATABRICKS_ENABLED = process.env.DATABRICKS_ENABLED === 'true'

if (BTP_ENABLED) {
  console.log('SAP BTP write-back ENABLED — routing through BAPI_PRICES_CONDITIONS')
} else {
  console.log('SAP BTP write-back DISABLED — mock ZMKD responses active')
}
if (DATABRICKS_ENABLED) {
  console.log('Databricks items feed ENABLED — querying ahold_poc.gold.recommended_price')
} else {
  console.log('Databricks items feed DISABLED — mock items active')
}

// Lazy-load clients only when enabled (avoids import errors when env vars absent)
let _databricksClient = null
async function getDatabricksClient() {
  if (!_databricksClient) {
    _databricksClient = await import('./databricks-client.js')
  }
  return _databricksClient
}

const MOCK_ITEMS = [
  { item: { item_id: 'SKU-001', name_fr: 'Fraises biologiques 500g',      name_nl: 'Biologische aardbeien 500g',        current_price: 3.49, stock: 17, hours_to_close: 6, sales_velocity_7d: 4.2 }, rec: { discount_pct: 0.30, recommended_price: 2.44, confidence: 0.89, manager_required: false } },
  { item: { item_id: 'SKU-002', name_fr: 'Poulet rôti Label Rouge 1.2kg', name_nl: 'Geroosterde kip Label Rouge 1.2kg', current_price: 9.99, stock:  8, hours_to_close: 3, sales_velocity_7d: 2.8 }, rec: { discount_pct: 0.40, recommended_price: 5.99, confidence: 0.97, manager_required: false } },
  { item: { item_id: 'SKU-003', name_fr: 'Croissants beurre x6',          name_nl: 'Boter croissants x6',               current_price: 2.89, stock: 24, hours_to_close: 5, sales_velocity_7d: 9.1 }, rec: { discount_pct: 0.30, recommended_price: 2.02, confidence: 0.92, manager_required: false } },
  { item: { item_id: 'SKU-004', name_fr: 'Saumon fumé 200g',              name_nl: 'Gerookte zalm 200g',                current_price: 5.99, stock: 12, hours_to_close: 7, sales_velocity_7d: 3.4 }, rec: { discount_pct: 0.20, recommended_price: 4.79, confidence: 0.79, manager_required: false } },
  { item: { item_id: 'SKU-005', name_fr: 'Pain de campagne 400g',         name_nl: 'Boerenbrood 400g',                  current_price: 2.49, stock: 31, hours_to_close: 4, sales_velocity_7d: 11.6 }, rec: { discount_pct: 0.30, recommended_price: 1.74, confidence: 0.91, manager_required: false } },
]

let _btpClient = null
async function getBtpClient() {
  if (!_btpClient) {
    _btpClient = await import('./btp-client.js')
  }
  return _btpClient
}

// Track approved items for idempotency (in-memory; Redis in production)
const approved = new Set()

function zmkdConditionRecord() {
  return String(Math.floor(Math.random() * 9_000_000_000) + 1_000_000_000).padStart(10, '0')
}

function isoDate(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().split('T')[0]
}

app.get('/api/items', async (req, res) => {
  if (!DATABRICKS_ENABLED) {
    return res.json(MOCK_ITEMS)
  }
  try {
    const { fetchRecommendations } = await getDatabricksClient()
    const store_id = req.query.store_id || 'BE01'
    const items = await fetchRecommendations(store_id)
    res.json(items)
  } catch (err) {
    console.error('Databricks query error:', err.message)
    res.status(502).json({ error: 'databricks_error', message: err.message })
  }
})

app.post('/api/approve', async (req, res) => {
  const { item_id, discount_pct, manager_override = false, store_id = 'BE01' } = req.body

  if (!item_id || discount_pct === undefined) {
    return res.status(400).json({ error: 'item_id and discount_pct required' })
  }

  // BRE guardrail — discount > 50% requires manager_override
  if (discount_pct > 0.5 && !manager_override) {
    return res.status(403).json({ error: 'manager_approval_required', discount_pct })
  }

  if (approved.has(item_id)) {
    return res.json({ status: 'already_applied', condition_record: null })
  }

  const valid_from = isoDate(0)
  const valid_to   = isoDate(1)

  if (BTP_ENABLED) {
    try {
      const { callBapiPricesConditions } = await getBtpClient()
      const bapi = await callBapiPricesConditions({
        item_id, store_id, discount_pct, valid_from, valid_to,
      })
      approved.add(item_id)
      return res.json({ ...bapi, discount_pct, valid_from, valid_to })
    } catch (err) {
      console.error('BAPI_PRICES_CONDITIONS error:', err.message)
      // A004 lock or transient error — surface to manager, never silent success
      return res.status(502).json({
        error:   'bapi_error',
        message: err.message,
        hint:    'Mise a jour en attente — reessayer dans 30s.',
      })
    }
  }

  // Phase 2A mock path
  approved.add(item_id)
  res.json({
    status:           'zmkd_queued',
    condition_record: zmkdConditionRecord(),
    condition_type:   'ZMKD',
    table:            'A004',
    discount_pct,
    valid_from,
    valid_to,
  })
})

app.post('/api/reject', (req, res) => {
  const { item_id, reason_code = 'associate_judgement' } = req.body

  if (!item_id) {
    return res.status(400).json({ error: 'item_id required' })
  }

  res.json({ status: 'rejected', item_id, reason_code })
})

app.listen(PORT, () => {
  console.log(`BFF running on http://localhost:${PORT} (BTP_ENABLED=${BTP_ENABLED})`)
})
