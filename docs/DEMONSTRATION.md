# Présentation orale en français

Durée indicative : cinq minutes.

1. « FedTrace permet de retrouver les contributions qui ont produit le modèle utilisé pour une décision. Toutes les données sont synthétiques et cette simulation n'a aucune validation clinique. Les cliniques sont trois processus sur le même poste. » Montrer le tableau de bord et les reçus.
2. « Une clinique signe l'empreinte de son delta. Le serveur attend la confirmation de toutes les contributions avant d'agréger. Les poids et les données restent hors chaîne. » Déplier une empreinte et un reçu ; montrer les échantillons déclarés.
3. « La certification conditionne l'inférence. » Exécuter un cas dans Simulation, afficher les contributions au logit, vérifier l'explication puis ouvrir la provenance jusqu'au round initial.
4. Exécuter `python -m scripts.scenarios`. « B modifie les octets d'une explication : la comparaison d'empreintes échoue. C remplace le modèle : l'inférence est refusée. D réutilise exactement les mêmes deltas empoisonnés : le filtre robuste rejette la clinique 3, FedAvg l'intègre. Les deux résultats sont enregistrés. » Montrer `reports/scenarios.json`.
5. « E coupe le registre après l'entraînement, conserve trois contributions en attente, ouvre un nouveau processus puis reprend sans doublon. » Montrer le résultat E. Dans la console en mode démo, couper le registre ; une inférence échoue avec `ledger_unavailable` ; le rétablir.
6. « Le simulateur local et le nœud EVM sont distincts. Les reçus EVM sont de vraies transactions sur une chaîne de développement, sans consensus distribué entre cliniques. » Montrer `reports/evm-validation.json` et la note de choix technologique.
7. Afficher le graphique de benchmark. « La taille du hash est fixe ; les coûts de métadonnées, disque et calcul ne le sont pas. La certification prouve une provenance sous nos hypothèses de confiance, pas une qualité clinique. Les clés sont administrées localement et les volumes déclarés ne sont pas vérifiés indépendamment. »
