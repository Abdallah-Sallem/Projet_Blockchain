export function stateLabel(state) {
  return (
    {
      confirmed: "Confirmé",
      pending: "En attente",
      submitted: "Soumis",
      failed: "Échec",
      tampered: "Falsifié",
      unavailable: "Indisponible",
      available: "Disponible",
      rejected: "Rejeté",
      uncertified: "Non certifié",
    }[state] ?? state
  );
}
