export default function ErrorState({ t, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      <div className="text-5xl mb-4">⚠️</div>
      <p className="font-semibold text-slate-700 text-lg mb-2">{t.errorTitle}</p>
      <button
        onClick={onRetry}
        className="mt-4 bg-slate-900 hover:bg-slate-700 text-white text-sm font-semibold px-6 py-2.5 rounded-xl transition-colors"
      >
        {t.errorRetry}
      </button>
    </div>
  )
}
