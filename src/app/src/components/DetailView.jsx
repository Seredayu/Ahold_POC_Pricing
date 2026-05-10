export default function DetailView({ item, rec, lang, t, onApprove, onReject, onClose }) {
  const name = lang === 'fr' ? item.name_fr : item.name_nl

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

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-start gap-3 mb-4">
        <button
          onClick={onClose}
          className="shrink-0 text-slate-400 hover:text-slate-600 text-xl leading-none mt-0.5"
          aria-label="Close"
        >
          ←
        </button>
        <p className="font-semibold text-slate-900 text-base leading-snug">{name}</p>
      </div>

      <div className="bg-slate-50 rounded-xl p-4 mb-4">
        <p className="text-sm text-slate-600 leading-relaxed">
          {t.reason(item.stock, item.sales_velocity_7d, item.hours_to_close)}
        </p>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-baseline gap-2">
          <span className="text-slate-400 line-through text-base">€{item.current_price.toFixed(2)}</span>
          <span className="text-slate-900 font-bold text-2xl">€{rec.recommended_price.toFixed(2)}</span>
        </div>
        <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${discountColor}`}>
          {t.discountLabel(rec.discount_pct)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4 text-center">
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">Stock</p>
          <p className="font-semibold text-slate-900 text-sm">{t.stockLabel(item.stock)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">Expiry</p>
          <p className="font-semibold text-slate-900 text-sm">{t.expiryLabel(item.hours_to_close)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">AI</p>
          <p className={`font-semibold text-sm ${confidenceColor}`}>{t.confidence(rec.confidence)}</p>
        </div>
      </div>

      {rec.confidence < 0.5 && (
        <p className="mb-3 text-sm text-red-600 font-medium bg-red-50 rounded-xl px-4 py-2.5">
          ⚠ {t.lowConfidence}
        </p>
      )}
      {rec.manager_required && (
        <p className="mb-3 text-sm text-purple-600 font-medium bg-purple-50 rounded-xl px-4 py-2.5">
          👤 {t.managerRequired}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => onApprove(item, rec)}
          className="flex-1 bg-green-600 hover:bg-green-700 active:bg-green-800 text-white text-sm font-semibold py-3 rounded-xl transition-colors"
        >
          {t.apply}
        </button>
        <button
          onClick={() => onReject(item)}
          className="flex-1 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-700 text-sm font-semibold py-3 rounded-xl transition-colors"
        >
          {t.reject}
        </button>
      </div>
    </div>
  )
}
