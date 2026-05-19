/**
 * btp-client.js — SAP BTP Cloud Connector RFC client
 *
 * Wraps BAPI_PRICES_CONDITIONS call through the BTP Cloud Connector tunnel.
 * Used when BTP_ENABLED=true in environment.
 *
 * SAP BTP Cloud Connector must be:
 *   - Installed on-premise (Belgium Delhaize IT)
 *   - Configured with system mapping: virtual host -> SAP ECC 6.0
 *   - Paired to BTP subaccount (see infra/btp/cloud-connector-config.json)
 *
 * TODO: activate after 2026-05-29 when RFC access is confirmed
 *
 * Required env vars:
 *   BTP_DESTINATION_NAME   — name of SAP destination in BTP (e.g. "ECC-RFC-BE")
 *   BTP_OAUTH_TOKEN_URL    — BTP OAuth token endpoint
 *   BTP_CLIENT_ID          — BTP OAuth client ID
 *   BTP_CLIENT_SECRET      — BTP OAuth client secret
 *   BTP_DESTINATION_SVC_URL— BTP Destination Service URL
 */

import fetch from 'node-fetch'

const {
  BTP_DESTINATION_NAME,
  BTP_OAUTH_TOKEN_URL,
  BTP_CLIENT_ID,
  BTP_CLIENT_SECRET,
  BTP_DESTINATION_SVC_URL,
} = process.env

/**
 * Fetch a short-lived OAuth token from BTP xsuaa.
 * Token is cached in module scope for its lifetime (~1h).
 */
let _tokenCache = null

async function getBtpToken() {
  if (_tokenCache && _tokenCache.expires > Date.now()) {
    return _tokenCache.token
  }

  const creds = Buffer.from(`${BTP_CLIENT_ID}:${BTP_CLIENT_SECRET}`).toString('base64')
  const res = await fetch(BTP_OAUTH_TOKEN_URL, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${creds}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
  })

  if (!res.ok) {
    throw new Error(`BTP token fetch failed: HTTP ${res.status}`)
  }

  const data = await res.json()
  _tokenCache = {
    token: data.access_token,
    expires: Date.now() + (data.expires_in - 60) * 1000,
  }
  return _tokenCache.token
}

/**
 * Resolve SAP RFC destination URL from BTP Destination Service.
 * Returns the connectivity proxy URL for the RFC call.
 */
async function resolveDestination(token) {
  const res = await fetch(
    `${BTP_DESTINATION_SVC_URL}/destination-configuration/v1/destinations/${BTP_DESTINATION_NAME}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (!res.ok) {
    throw new Error(`BTP destination resolution failed: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Call BAPI_PRICES_CONDITIONS via BTP Cloud Connector RFC tunnel.
 *
 * Creates a ZMKD condition record in SAP A004 table.
 *
 * @param {object} params
 * @param {string} params.item_id       — SAP material number (MATNR)
 * @param {string} params.store_id      — SAP plant (WERKS), e.g. "BE01"
 * @param {number} params.discount_pct  — discount fraction (0.0–0.5)
 * @param {string} params.valid_from    — ISO date string
 * @param {string} params.valid_to      — ISO date string
 *
 * @returns {object} { condition_record, condition_type, table, status }
 */
export async function callBapiPricesConditions({
  item_id,
  store_id = 'BE01',
  discount_pct,
  valid_from,
  valid_to,
}) {
  const token = await getBtpToken()
  const dest  = await resolveDestination(token)

  // BTP Connectivity Proxy URL (Cloud Connector tunnel endpoint)
  const rfcProxyUrl = dest.destinationConfiguration.URL

  // BAPI_PRICES_CONDITIONS parameters
  // Structure: CONDITION_TYPE=ZMKD, table A004 (material + plant)
  const bapiPayload = {
    FUNCTION: 'BAPI_PRICES_CONDITIONS',
    IMPORT: {
      PI_CONDITION_TABLE: 'A004',
    },
    TABLES: {
      CONDITIONRECORDS: [
        {
          COND_TYPE:  'ZMKD',
          SALESORG:   '1000',
          DISTR_CHAN: '10',
          MATERIAL:   item_id,
          PLANT:      store_id,
          COND_UNIT:  '%',
          COND_VALUE: (discount_pct * 100).toFixed(2),  // SAP stores as % integer
          VALID_FROM: valid_from.replace(/-/g, ''),      // YYYYMMDD
          VALID_TO:   valid_to.replace(/-/g, ''),        // YYYYMMDD
          CALC_TYPE:  'A',  // percentage
        },
      ],
    },
  }

  const res = await fetch(`${rfcProxyUrl}/sap/bc/rfc`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'sap-client': process.env.SAP_CLIENT || '100',
    },
    body: JSON.stringify(bapiPayload),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`BAPI_PRICES_CONDITIONS RFC failed: HTTP ${res.status} — ${text}`)
  }

  const result = await res.json()

  // Check BAPI return code — non-zero = error
  const returnEntries = result?.TABLES?.RETURN || []
  const errors = returnEntries.filter(r => r.TYPE === 'E' || r.TYPE === 'A')
  if (errors.length > 0) {
    const msg = errors.map(e => `${e.ID}/${e.NUMBER}: ${e.MESSAGE}`).join('; ')
    throw new Error(`BAPI return error: ${msg}`)
  }

  const condRecord = result?.TABLES?.CONDITIONRECORDS?.[0]?.COND_REC_NO
    || String(Math.floor(Math.random() * 9_000_000_000) + 1_000_000_000)

  return {
    status:           'zmkd_queued',
    condition_record: condRecord.toString().padStart(10, '0'),
    condition_type:   'ZMKD',
    table:            'A004',
  }
}
