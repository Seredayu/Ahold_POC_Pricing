import { useState, useEffect } from 'react'
import RecommendationCard from './components/RecommendationCard'
import ConfirmationBanner from './components/ConfirmationBanner'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import { MOCK_ITEMS } from './lib/mockData'
import { getRecommendation } from './lib/decisionTable'
import { postApprove, postReject } from './lib/api'
import strings from './lib/i18n'

function buildQueue(items) {
  return items
    .map(item => ({ item, rec: getRecommendation(item) }))
    .filter(({ rec }) => rec.recommended)
    .sort((a, b) => a.item.hours_to_close - b.item.hours_to_close)
}

export default function App() {
  const [lang, setLang] = useState('fr')
  const t = strings[lang]

  const [queue] = useState(() => buildQueue(MOCK_ITEMS))
  const [dismissed, setDismissed] = useState(new Set())
  const [banner, setBanner] = useState(null)
  const [error, setError] = useState(false)
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])

  const visibleQueue = queue.filter(({ item }) => !dismissed.has(item.item_id))

  async function handleApprove(item, rec) {
    if (dismissed.has(item.item_id)) {
      setBanner({ message: t.alreadyApplied, sub: null })
      return
    }
    try {
      const data = await postApprove(item.item_id, rec.discount_pct)
      if (data.status === 'already_applied') {
        setBanner({ message: t.alreadyApplied, sub: null })
        return
      }
      setDismissed(prev => new Set([...prev, item.item_id]))
      setBanner({
        message: t.synced,
        sub: data.condition_record ? t.syncedRef(data.condition_record) : null,
        itemId: item.item_id,
      })
      setError(false)
    } catch {
      setError(true)
    }
  }

  async function handleReject(item) {
    try {
      await postReject(item.item_id)
      setDismissed(prev => new Set([...prev, item.item_id]))
      setBanner({ message: t.rejected, sub: null })
      setError(false)
    } catch {
      setError(true)
    }
  }

  function handleUndo() {
    if (!banner?.itemId) return
    setDismissed(prev => {
      const next = new Set(prev)
      next.delete(banner.itemId)
      return next
    })
    setBanner(null)
  }

  function handleRetry() {
    setError(false)
    setDismissed(new Set())
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between sticky top-0 z-40">
        <h1 className="font-bold text-slate-900 text-lg">{t.appTitle}</h1>
        <div className="flex items-center gap-3">
          {offline && (
            <span className="text-xs text-amber-600 font-medium bg-amber-50 px-2.5 py-1 rounded-full">
              Offline
            </span>
          )}
          <button
            onClick={() => setLang(l => l === 'fr' ? 'nl' : 'fr')}
            className="text-xs font-semibold text-slate-500 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg transition-colors"
          >
            {t.langToggle}
          </button>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-4 space-y-3">
        {error ? (
          <ErrorState t={t} onRetry={handleRetry} />
        ) : visibleQueue.length === 0 ? (
          <EmptyState t={t} />
        ) : (
          visibleQueue.map(({ item, rec }) => (
            <RecommendationCard
              key={item.item_id}
              item={item}
              rec={rec}
              lang={lang}
              t={t}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))
        )}
      </main>

      {banner && (
        <ConfirmationBanner
          key={banner.message + (banner.sub || '')}
          message={banner.message}
          subMessage={banner.sub}
          onUndo={banner.itemId ? handleUndo : null}
          t={t}
        />
      )}

      {offline && (
        <div className="fixed top-14 left-4 right-4 z-50">
          <div className="bg-amber-500 text-white text-xs font-medium text-center py-1.5 rounded-lg">
            {t.offlineToast}
          </div>
        </div>
      )}
    </div>
  )
}
