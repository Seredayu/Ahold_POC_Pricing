export default function EmptyState({ t }) {
  const nextCheck = new Date()
  nextCheck.setHours(14, 0, 0, 0)
  if (nextCheck <= new Date()) nextCheck.setDate(nextCheck.getDate() + 1)
  const timeStr = nextCheck.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      <div className="text-5xl mb-4">🌿</div>
      <p className="font-semibold text-slate-700 text-lg mb-2">{t.emptyTitle}</p>
      <p className="text-slate-400 text-sm">{t.emptyBody(timeStr)}</p>
    </div>
  )
}
