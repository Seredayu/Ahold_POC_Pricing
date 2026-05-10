import { useEffect, useState } from 'react'

export default function ConfirmationBanner({ message, subMessage, onUndo, t }) {
  const [visible, setVisible] = useState(true)
  const [undoActive, setUndoActive] = useState(true)

  useEffect(() => {
    const undoTimer = setTimeout(() => setUndoActive(false), 30000)
    const hideTimer = setTimeout(() => setVisible(false), 5000)
    return () => { clearTimeout(undoTimer); clearTimeout(hideTimer) }
  }, [])

  if (!visible) return null

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 animate-in slide-in-from-bottom-4 duration-300">
      <div className="bg-green-600 text-white rounded-2xl px-4 py-3 shadow-lg flex items-center gap-3">
        <span className="text-lg">✓</span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm">{message}</p>
          {subMessage && <p className="text-green-100 text-xs mt-0.5">{subMessage}</p>}
        </div>
        {undoActive && onUndo && (
          <button
            onClick={onUndo}
            className="shrink-0 text-green-100 hover:text-white text-sm font-semibold underline"
          >
            {t.undo}
          </button>
        )}
      </div>
    </div>
  )
}
