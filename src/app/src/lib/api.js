const BASE = import.meta.env.VITE_API_URL || '/api'

// Track approved items to enforce idempotency client-side.
const approved = new Set()

export async function fetchItems() {
  const res = await fetch(`${BASE}/items`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function postApprove(item_id, discount_pct, manager_override = false) {
  if (approved.has(item_id)) {
    return { status: 'already_applied', condition_record: null }
  }

  const res = await fetch(`${BASE}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id, discount_pct, manager_override }),
  })

  if (!res.ok) throw new Error(`${res.status}`)

  const data = await res.json()
  approved.add(item_id)
  return data
}

export async function uploadSkus(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/upload-skus`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function postReject(item_id, reason_code = 'associate_judgement') {
  const res = await fetch(`${BASE}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id, reason_code }),
  })

  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}
