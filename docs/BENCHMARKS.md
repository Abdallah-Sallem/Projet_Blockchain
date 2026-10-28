# Protocole de mesure

Commande : `python -m scripts.benchmark --repeats 3 --dimensions 6 600`.

Pour chaque dimension et graine 42, 43, 44 : trois processus cliniques, deux époques, mêmes partitions synthétiques 60/20/20, même modèle linéaire et même agrégateur robuste. L'entraînement est exécuté **une fois**, chronométré, puis ses mêmes deltas sont rejoués dans les trois configurations. Les durées de round additionnent cette durée d'entraînement partagée et les opérations effectivement mesurées pour chaque configuration. Il s'agit d'un plan apparié, pas de trois mesures indépendantes de temps mur total. Ne pas interpréter leurs écarts-types comme trois réplications indépendantes par mode.

1. Fédération seule : agrégation et évaluation, aucune écriture de preuve.
2. Modèle seul : un checkpoint global indépendant ancré sans généalogie de contributions. Pour cette ablation, le checkpoint emploie le schéma racine du registre (round 0, parent nul), sans la porte d'inférence. Cela mesure le coût d'une preuve globale, pas un parcours fédéré auditable complet.
3. Contributions et certification : trois contributions confirmées avant agrégation, puis le modèle round 1 avec parent et références. Les essais de certification et de falsification sont mesurés séparément, après le temps du round.

Le modèle initial, l'enrôlement d'identités et les décisions des essais sont exclus des compteurs par round. Le coût d'ancrage inclut signatures serveur, mises en file, validation et confirmations locales ; les signatures cliniques appartiennent à la durée d'entraînement commune. Le mode sans registre a un faible coût de chronomètre dans le champ anchoring_seconds ; il ne s'agit pas d'une transaction.

Le nombre de cliniques et les schémas restent constants entre tailles ; seuls dimensions et résultats numériques changent. L'empreinte garde 64 caractères, mais les tailles des métadonnées varient (dimensions, nombres, métriques, timestamps). Il ne faut pas assimiler empreinte de taille fixe et coût transactionnel total constant. Le coût du calcul de l'empreinte et du stockage hors chaîne augmente avec les poids.

Les octets écrits correspondent à la sérialisation JSON des enveloppes signées effectivement ajoutées. La croissance physique est la différence de taille des fichiers SQLite après checkpoint WAL : une écriture peut consommer une page déjà allouée et afficher zéro octet de croissance. L'initialisation de la base n'est pas incluse. Les mesures ne sont pas des coûts EVM en gaz ; les reçus EVM sont fournis séparément dans les preuves de validation.

Le temps de reconstruction inclut la lecture et la vérification de la chaîne locale jusqu'au modèle demandé. Les parcours de benchmark portent sur un round ; le scénario A et la démonstration EVM parcourent plusieurs rounds. Pour chaque paire taille/graine, cinq essais de falsification d'explication, cinq inférences sous registre sain et un refus pour panne sont réalisés en mode complet. Les taux ne sont pas une preuve statistique de sécurité générale : ils concernent uniquement ces mutations et ces cas synthétiques.

Les essais ont été exécutés sur le poste Windows de développement, avec d'autres vérifications potentiellement concurrentes : les mesures sont descriptives et non une étude de capacité isolée. Voir le rapport pour les valeurs réelles ; les fichiers CSV/JSON sont la source des graphiques PNG/SVG. Aucun résultat « négligeable » n'est supposé avant lecture des mesures.
