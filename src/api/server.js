import express from 'express'
import cors from 'cors'

const app = express()
app.use(cors())
app.use(express.json())

const PORT = process.env.PORT || 3001

// Track approved items for idempotency
const approved = new Set()

function zmkdConditionRecord() {
  return String(Math.floor(Math.random() * 9_000_000_000) + 1_000_000_000).padStart(10, '0')
}

function isoDate(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().split('T')[0]
}

app.post('/api/approve', (req, res) => {
  const { item_id, discount_pct, manager_override = false } = req.body

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

  approved.add(item_id)

  res.json({
    status: 'zmkd_queued',
    condition_record: zmkdConditionRecord(),
    condition_type: 'ZMKD',
    table: 'A004',
    discount_pct,
    valid_from: isoDate(0),
    valid_to: isoDate(1),
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
  console.log(`Mock BFF running on http://localhost:${PORT}`)
})
