import { useState } from 'react'
import DetailView from './DetailView'

export default function RecommendationCard({ item, rec, lang, t, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false)

  const name = lang === 'fr' ? item.name_fr : item.name_nl
  const displayName = name.length > 42
    ? name.slice(0, 42).replace(/\s+\S*$/, '') + '…'
    : name

  const discountColor = rec.discount_pct >= 0.40
    ? 'bg-red-100 text-red-700'
    : rec.discount_pct >= 0.30
      ? 'bg-orange-100 text-orange-700'
      : 'bg-yellow-100 text-yellow-700'

  const confidenceColor = rec.confidence < 0.5
    ? 'text-red-600'
    : rec.confidence < 0.75
      ? 'text-yellow-600'
      : 'text-green-600'

  if (expanded) {
    return (
      <DetailView
        item={item}
        rec={rec}
        lang={lang}
        t={t}
        onApprove={onApprove}
        onReject={onReject}
        onClose={() => setExpanded(false)}
      />
    )
  }

  return (
    <div
      className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 cursor-pointer active:scale-[0.98] transition-transform"
      onClick={() => setExpanded(true)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-900 text-sm leading-snug truncate">{displayName}</p>
          <p className="text-xs text-slate-500 mt-1">{t.reason(item.stock, item.sales_velocity_7d, item.hours_to_close)}</p>
        </div>
        <span className={`shrink-0 text-xs font-bold px-2 py-1 rounded-full ${discountColor}`}>
          {t.discountLabel(rec.discount_pct)}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div className="flex items-baseline gap-1">
          <span className="text-slate-400 line-through text-sm">€{item.current_price.toFixed(2)}</span>
          <span className="text-slate-900 font-bold text-lg">€{rec.recommended_price.toFixed(2)}</span>
        </div>
        <div className="flex-1" />
        <span className={`text-xs font-medium ${confidenceColor}`}>
          {t.confidence(rec.confidence)}
        </span>
        <span className="text-xs text-slate-400">{t.expiryLabel(item.hours_to_close)}</span>
      </div>

      {rec.confidence < 0.5 && (
        <p className="mt-2 text-xs text-red-600 font-medium">⚠ {t.lowConfidence}</p>
      )}
      {rec.manager_required && (
        <p className="mt-2 text-xs text-purple-600 font-medium">👤 {t.managerRequired}</p>
      )}

      <div className="mt-4 flex gap-2" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => onApprove(item, rec)}
          className="flex-1 bg-green-600 hover:bg-green-700 active:bg-green-800 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {t.apply}
        </button>
        <button
          onClick={() => onReject(item)}
          className="flex-1 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-700 text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {t.reject}
        </button>
      </div>
    </div>
  )
}
