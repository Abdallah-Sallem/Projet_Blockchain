# Choix du registre

La spécification Projet 5 est la source des exigences. Les bibliothèques et formats suivants sont des choix de réalisation.

| Critère | Registre local chaîné | Fabric ou Besu permissionné | Chaîne publique EVM |
|---|---|---|---|
| Identités | Clés secp256k1 autorisées, signatures vérifiables | MSP Fabric ou comptes et permissionnement Besu | Comptes pseudonymes et liste autorisée |
| Écriture et validation | Validateur Python, SQLite transactionnel | Contrat et consensus du consortium | Contrat et consensus public |
| Métadonnées | Accès machine locale | Visibles au consortium | Visibles publiquement, durablement |
| Historique | Index par clé, chaîne SHA-256 | Événements et stockage du contrat | Événements, lecture RPC |
| Installation | Python uniquement | Nœuds, clés, réseau et exploitation | RPC, portefeuille et financement |
| Débit | À mesurer sur ce poste | Dépend du consensus et du réseau | Dépend du réseau et de la charge |
| Coût | Disque et CPU | Infrastructure et exploitation | Gaz et infrastructure RPC |

Décision : valider le parcours complet sur SQLite puis conserver la même interface pour un contrat EVM. Ganache est un nœud de développement local ; il ne constitue pas un consortium distribué. Besu QBFT est la cible de déploiement permissionné, dont la mise en production n'est pas revendiquée ici. Aucun frais public n'est engagé.

Le contrat EVM authentifie une signature secp256k1 sur le SHA-256 des octets JSON canoniques, vérifie les dépendances structurées, garde les octets de métadonnées et émet un événement. Le relais autorisé reste responsable de la cohérence entre JSON et champs structurés et des règles métier détaillées ; ce périmètre de confiance est explicite. Le registre local est modifiable par son administrateur : le chaînage détecte des modifications sans engagement externe, mais ne protège pas contre une réécriture totale.

Hors chaîne : poids NPZ sans pickle, explications JSON exactes, cas synthétiques et clés privées dans runtime ignoré par Git. La fédération ne garantit pas la confidentialité ; aucun mécanisme de confidentialité différentielle ou d'agrégation sécurisée n'est activé par défaut.
