# FedTrace

Prototype académique reproductible de provenance d'un apprentissage fédéré. Trois cliniques au minimum sont des **processus Python distincts sur une seule machine**. Les données, cas et résultats sont synthétiques, sans validation clinique. Ne pas utiliser sur des patients réels.

Le parcours exécutable est : entraînement local → mises à jour signées → confirmation des contributions → agrégation → confirmation du modèle → certification avant inférence → explication exacte et décision ancrées → arbre de provenance jusqu'au modèle initial.

## Démarrage sous Windows

Prérequis testés : Python 3.9, Node 22, Git ; environ 2 Go disponibles pour PyTorch et les dépendances. Depuis la racine du dépôt :

```powershell
.\demo.ps1
```

Le script installe les dépendances si nécessaire, construit l'interface, exécute trois rounds avec trois processus cliniques et un diagnostic vérifié, puis sert **http://127.0.0.1:8000**. Coller le jeton affiché dans « Authentification locale des actions » pour lancer une expérience ou un cas synthétique. Les lectures d'audit sont accessibles localement sans jeton ; les écritures exigent le jeton du dépositaire. Le service se lie à l'interface locale uniquement.

Installation et commandes explicites :

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
# Variante CPU, pour éviter les distributions CUDA sur Linux :
# .venv/bin/python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python -m fedtrace.cli demo --rounds 3 --clinics 3 --epochs 6 --seed 42
$env:FEDTRACE_DEMO='1'
.\.venv\Scripts\python -m fedtrace.cli serve
```

Sous Linux, remplacer `.venv\Scripts\python` par `.venv/bin/python`. Le script PowerShell est spécifique à Windows ; les commandes Python et npm sont portables. `requirements-lock.txt` fige l'environnement Python réellement testé, avec PyTorch CPU ; installer ce verrou avec `--extra-index-url https://download.pytorch.org/whl/cpu`. Les deux `package-lock.json` figent les dépendances JavaScript.

```powershell
.\.venv\Scripts\python -m fedtrace.cli demo --home runtime/poison --strategy robust --poison
.\.venv\Scripts\python -m fedtrace.cli token
.\.venv\Scripts\python -m fedtrace.cli status
.\.venv\Scripts\python -m fedtrace.cli resume
```

La configuration Python `Service.configure` expose aussi dimensions, partitions non IID, nombre de cliniques, rounds, époques, graine et stratégie. Le processus de fond reprend automatiquement les ancrages et le round actif au redémarrage du serveur. `resume` effectue une étape explicite en ligne de commande.

## Blockchain EVM réelle en développement

Le mode par défaut est un **simulateur de registre chaîné persistant**, pas une blockchain. Le second adaptateur envoie de vraies transactions vers un **nœud EVM de développement Ganache**, sans réseau public ni argent réel.

Terminal 1 :

```powershell
cd contracts
npm ci
npm run compile
npm run chain
```

Terminal 2, depuis la racine :

```powershell
.\.venv\Scripts\python -m scripts.deploy
.\.venv\Scripts\python -m scripts.validate_evm
$env:FEDTRACE_LEDGER='evm'
.\.venv\Scripts\python -m fedtrace.cli demo --home runtime/evm-demo --rounds 2
.\.venv\Scripts\python -m fedtrace.cli serve --home runtime/evm-demo --port 8001
```

`deploy` utilise exclusivement le compte déverrouillé d'un réseau de développement pour financer une nouvelle clé de passerelle, puis écrit la configuration privée dans `runtime/evm/deployment.json`, ignorée par Git. Aucun secret de portefeuille n'est commité. Pour revenir au simulateur : `$env:FEDTRACE_LEDGER='local'`.

Le contrat vérifie les signatures des auteurs, leurs rôles, les parents, les rounds, les références et l'idempotence. La passerelle autorisée valide en plus les métadonnées JSON et leur correspondance aux champs structurés. Cette confiance dans la passerelle est une limite du prototype, décrite dans [le rapport](docs/RAPPORT.md). Un seul nœud ne prouve aucune tolérance aux fautes distribuées. [Le guide Besu](docs/BESU.md) décrit l'installation restante pour un consortium ; aucun déploiement distribué n'est revendiqué.

## Vérifications et expériences

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m scripts.scenarios
# Pour une seule démonstration : --scenario A (ou B, C, D, E)
.\.venv\Scripts\python -m scripts.benchmark --repeats 3 --dimensions 6 600
cd contracts
npm test
cd ../frontend
npm run build
npm test
npx playwright install chromium
# Lancer le serveur avec une démo terminée sur le port 8000 avant ce test :
npx playwright test
```

Les cinq scénarios sont assertés ; une condition attendue non satisfaite fait échouer le script. A : nominal et provenance ; B : octets d'explication falsifiés ; C : poids substitués sans ancrage ; D : **mêmes mises à jour empoisonnées** utilisées pour robuste et FedAvg, avec deux enregistrements de modèle ; E : panne après entraînement, attente durable de trois contributions, nouveau processus, reprise et absence de doublons.

Les mesures exportées sont dans [benchmarks/raw.csv](benchmarks/raw.csv), [benchmarks/raw.json](benchmarks/raw.json), [la synthèse](benchmarks/summary.json) et [le graphique](benchmarks/comparison.png). Lire [le protocole et ses limites](docs/BENCHMARKS.md) avant toute interprétation. Les résultats observés et commandes exécutées sont consignés dans [reports/VALIDATION.md](reports/VALIDATION.md).

## Organisation

| Répertoire | Fonction |
|---|---|
| `fedtrace/canonical.py` | Format canonique explicite et SHA-256 |
| `fedtrace/identity.py` | Clés et signatures secp256k1 récupérables |
| `fedtrace/ledger.py`, `evm.py` | Registre local et adaptateur RPC EVM |
| `fedtrace/outbox.py`, `service.py` | Reprise durable et portes de confirmation |
| `fedtrace/federation.py` | Travailleurs PyTorch et agrégateurs |
| `fedtrace/api.py`, `cli.py` | API FastAPI et commandes |
| `frontend/` | Console React et TypeScript en français |
| `contracts/` | Contrat Solidity, compilation, chaîne locale et tests |
| `scripts/`, `tests/` | Scénarios, mesures et vérification |
| `runtime/` | Secrets, modèles NPZ, explications, cas et bases locales ; ignoré par Git |

La spécification source est conservée dans `Projet 5.docx`. La [matrice de traçabilité](docs/EXIGENCES.md) relie les exigences à leur réalisation, aux preuves et à la documentation. Voir aussi la [note de choix technologique](docs/ADR-001-registre.md), [les schémas](docs/ARCHITECTURE.md) et [le script oral](docs/DEMONSTRATION.md).

## Limites essentielles

La fédération ne garantit pas la confidentialité ; les mises à jour peuvent divulguer de l'information. Le hachage ne chiffre rien. Les pseudonymes et probabilités sont des métadonnées potentiellement sensibles, même sans identifiant direct. La certification atteste une provenance enregistrée dans les hypothèses de confiance du déploiement, jamais une qualité clinique. Les volumes d'échantillons sont déclarés et non vérifiés indépendamment. Les clés des cliniques sont distinctes mais gérées par le même dépositaire local ; ce prototype ne démontre pas l'autonomie administrative de véritables établissements. Les permissions de stockage Windows héritent des ACL du compte : employer un répertoire privé et un disque chiffré pour tout usage dépassant les données synthétiques.
