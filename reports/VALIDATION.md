# Validation exécutée le 28 octobre 2026

Environnement réel : Windows, Python 3.9.13, PyTorch 2.8.0 CPU, NumPy 2.0.2, Node 22.16.0, Solidity 0.8.30, Vite 6.4.5. Les versions complètes sont figées dans les verrous. Les commandes ci-dessous ont été exécutées ; aucun résultat de CI distante n'est supposé.

| Commande ou contrôle | Résultat réellement observé | Preuve |
|---|---|---|
| `.venv\Scripts\python -m pytest -q --durations=5` | **24 passed**, 218,05 s | `backend-tests.txt` |
| `python -m scripts.scenarios` | **A, B, C, D, E réussis**, assertions actives | `scenarios-run.txt`, `scenarios.json` |
| `cd contracts; npm test` | Compilation solc réussie ; **1 test intégré réussi**, aucune assertion en échec | `contract-tests.txt` |
| `python -m scripts.deploy` puis `python -m scripts.validate_evm` | Contrat réellement déployé sur RPC Ganache ; **10 preuves confirmées**, historique de 3 modèles, vérification native de décision vraie, provenance jusqu'au root | `evm-run.txt`, `evm-validation.json` |
| `cd frontend; npm run build` | TypeScript et build Vite réussis | `frontend-checks.txt` |
| `cd frontend; npm test` | **1 test réussi**, états pending/submitted/confirmed/tampered/uncertified distincts | `frontend-checks.txt` |
| `cd frontend; npx playwright test` | **1 test navigateur réussi**, 15,5 s au total ; API réelle, décision, vérification, provenance, desktop et mobile, aucun pageerror | `browser-tests.txt`, captures PNG |
| Contrôle HTTP du téléchargement exact | Octets reçus identiques à `explanation_artifact` ; SHA-256 identique à l'ancrage ; décision confirmée | `api-smoke.json` |
| Contrôle HTTP de panne | POST diagnostic refusé **503 ledger_unavailable** ; registre rétabli et disponible ensuite | `api-smoke.json` |
| `python -m scripts.benchmark --repeats 3 --dimensions 6 600` | 18 lignes mesurées, 3 modes × 2 tailles × 3 graines ; CSV/JSON et graphiques générés | `../benchmarks/`, `benchmark-run.txt` |
| `npm audit --json` dans frontend | **0 vulnérabilité signalée** après mise à jour de Vite | `frontend-audit.json` |
| `npm audit --omit=dev --json` dans frontend | **0 vulnérabilité signalée** | `frontend-production-audit.json` |
| `npm audit --json` dans contracts | **36 signalements transitifs** : 2 faibles, 6 modérés, 23 élevés, 5 critiques ; chaîne d'outils de développement à qualifier avant exposition | `contracts-audit.json` |

Les essais backend couvrent notamment la reproductibilité interprocessus des empreintes, les types/formes/noms/valeurs, l'ordre des dictionnaires, les scalaires, les valeurs non finies, les signatures et auteurs non autorisés, les doublons, références invalides, décisions pending, modèles substitués, altération du chaînage, réponse perdue, crash avant enqueue et reprise durable. Le test du backoff utilise une horloge figée ; une version intermédiaire supposait à tort que les accès disque prenaient moins de 0,5 seconde et a été corrigée avant le passage final de la suite.

Les 30 mutations d'explication ont été détectées ; 0 faux refus sur 30 inférences sous registre sain ; 6 refus de disponibilité sur 6 pannes. Ces essais définis ne justifient aucune garantie statistique générale. Le protocole de temps est apparié : les trois modes partagent la même durée d'entraînement mesurée, puis rejouent les mêmes mises à jour. Le mode global seul est un checkpoint indépendant sans filiation de contributions, comme décrit dans `docs/BENCHMARKS.md`.

Les captures `dashboard-desktop.png` et `dashboard-mobile.png` ont été inspectées. Le test vérifie l'absence de débordement de page à 390 px ; les tableaux conservent un défilement horizontal local. Les clés privées, bases de travail, cas, modèles et jetons sont dans `runtime` et exclus de Git.

Non exécutés : consortium Besu/Fabric distribué entre organisations, déploiement public, réseau hospitalier, essais cliniques, tolérance à des validateurs byzantins et finalité sur chaîne publique. La configuration Besu est indicative et le guide indique le travail restant. Le réseau réellement utilisé est un nœud EVM de développement local, sans fonds réels. L'avertissement µWS sous Node 22 a entraîné un repli JavaScript de Ganache, sans empêcher les transactions ou tests.
