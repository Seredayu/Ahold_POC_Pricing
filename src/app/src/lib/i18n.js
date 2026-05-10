// Belgium bilingual: FR (default) + NL
// XAI reason codes required per Architecture.md + CAO/CCT Works Council gate.

const strings = {
  fr: {
    appTitle: 'Prix Frais',
    reason: (stock, velocity, hours) =>
      `${stock} unités. Vente prévue\u00a0: ${Math.round(velocity)}. Expire dans ${hours}h.`,
    apply: 'Appliquer la remise',
    reject: 'Refuser',
    synced: 'Prix mis à jour. Sync ESL en file.',
    syncedRef: (ref) => `Réf\u00a0: ${ref}`,
    rejected: 'Refus enregistré. Article suivant.',
    lowConfidence: 'Faible confiance — vérifier avant d\'appliquer.',
    managerRequired: 'Remise >50\u00a0% — approbation chef requise.',
    emptyTitle: 'Aucune recommandation pour le moment.',
    emptyBody: (time) => `Revérifiez après ${time}.`,
    errorTitle: 'Impossible de synchroniser.',
    errorRetry: 'Réessayer',
    offlineToast: 'Hors ligne — synchronisation à la reconnexion.',
    alreadyApplied: 'Déjà appliqué.',
    undo: 'Annuler',
    discountLabel: (pct) => `−${Math.round(pct * 100)}\u00a0%`,
    confidence: (score) => `${Math.round(score * 100)}\u00a0% confiance`,
    expiryLabel: (h) => `Expire dans ${h}h`,
    stockLabel: (n) => `${n} unités`,
    langToggle: 'NL',
  },
  nl: {
    appTitle: 'Verse Prijzen',
    reason: (stock, velocity, hours) =>
      `${stock} stuks. Verwachte verkoop\u00a0: ${Math.round(velocity)}. Vervalt in ${hours}u.`,
    apply: 'Korting toepassen',
    reject: 'Weigeren',
    synced: 'Prijs bijgewerkt. ESL sync in wachtrij.',
    syncedRef: (ref) => `Ref\u00a0: ${ref}`,
    rejected: 'Weigering geregistreerd. Volgend artikel.',
    lowConfidence: 'Lage betrouwbaarheid — controleer voor toepassing.',
    managerRequired: 'Korting >50\u00a0% — goedkeuring manager vereist.',
    emptyTitle: 'Momenteel geen aanbevelingen.',
    emptyBody: (time) => `Controleer opnieuw na ${time}.`,
    errorTitle: 'Synchronisatie mislukt.',
    errorRetry: 'Opnieuw proberen',
    offlineToast: 'Offline — synchronisatie bij herverbinding.',
    alreadyApplied: 'Al toegepast.',
    undo: 'Ongedaan maken',
    discountLabel: (pct) => `−${Math.round(pct * 100)}\u00a0%`,
    confidence: (score) => `${Math.round(score * 100)}\u00a0% betrouwbaarheid`,
    expiryLabel: (h) => `Vervalt in ${h}u`,
    stockLabel: (n) => `${n} stuks`,
    langToggle: 'FR',
  },
}

export default strings
