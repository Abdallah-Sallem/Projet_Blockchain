# Matrice de traçabilité

Source normative : `Projet 5.docx`, sections et tableaux intégralement lus. Le prompt joint ajoute des exigences de réalisation détaillées. Les choix Python/PyTorch/FastAPI/React, JSON, secp256k1, SQLite, filtre médian et EVM sont des décisions du prototype, non des technologies imposées par le document.

Statuts : **réalisé** signifie code et démonstration disponibles ; **limité** précise le périmètre effectivement validé, sans prétendre couvrir une infrastructure hospitalière.

| Exigence source ou complément | Implémentation | Test ou preuve | Documentation | Statut |
|---|---|---|---|---|
| Au moins trois cliniques, plusieurs rounds (§3, §9) | `federation.launch_clinics`, sous-processus | `test_nominal_provenance_and_processes`, A | README, rapport | Réalisé |
| Entraînement local sans échange de cas (§1, §5) | Jeu généré dans chaque worker, deltas seuls retournés | Inspection résultats workers, A | Rapport données | Réalisé, même hôte |
| Paramètres configurables | `Service.configure`, CLI, API | Tests, paramètres benchmark | README | Réalisé |
| Train, validation, test ; tailles inégales et non IID | Partition 60/20/20, 96/128/160 cas, décalages | Tests nominal, métadonnées signées | Rapport données | Réalisé |
| FedAvg pondéré (§5) | `aggregate(strategy='fedavg')` | `test_poison_same_updates`, D | Rapport agrégation | Réalisé |
| Agrégation robuste et exclusions (§5, §6) | Distance à médiane, moyenne pondérée | D et registre des raisons | Rapport limites | Réalisé, menace bornée |
| Poison ancré avant agrégation (§6) | Outbox puis vérification live | D, ordre des séquences testé | Architecture | Réalisé |
| Comparaison avec les mêmes deltas | D conserve NPZ et deux modèles | Empreintes identiques, inclusion FedAvg | Démonstration | Réalisé |
| Empreinte déterministe (§5, §8) | `canonical.tensor_bytes` | Reproductibilité interprocessus, ordre, dtype, formes | CANONICALISATION | Réalisé |
| Pas de pickle canonique | NPZ sans pickle et format binaire v1 | Aller-retour NPZ | CANONICALISATION | Réalisé |
| Rejet des entrées non finies | Contrôles NumPy et JSON | Paramétrisation NaN/Inf/objets | CANONICALISATION | Réalisé |
| Contributions avec identité, volume, confidentialité (§4 tableau) | Enveloppe signée dans chaque clinique | Tests signatures, A/D | Rapport identité | Réalisé |
| Signatures indépendamment vérifiables | personal-sign SHA-256, récupération d'adresse | Python et contrat | CANONICALISATION | Réalisé, dépositaire commun |
| Seules organisations autorisées écrivent (§8 tableau) | Roster de clés, rôles, jeton API | Auteurs non autorisés, contrat gateway | Rapport confiance | Réalisé, identités de laboratoire |
| Noms de clinique insuffisants comme authentification | API refuse champ clinic ; acteur lié à signature | Test API 422/401 | README | Réalisé |
| Modèle initial explicite | Racine round 0 signée | Provenance jusqu'au root | Architecture | Réalisé |
| Parent, stratégie, métriques, acceptations/rejets (§4 tableau) | Enregistrement global v1 | Tests références, A/D | Rapport | Réalisé |
| Incohérences et doublons conflictuels refusés | Validateur partagé, contrat structurel | Références absentes/autre round, duplications | Rapport registre | Réalisé |
| Append-only, horodatage, reçus, schéma | SQLite chaîne SHA-256 et contrat Solidity | Test altération chaîne, EVM demo | ADR | Réalisé |
| Historique complet d'une clé (§5) | `LedgerQueries.history`, API ; contrat history | Historique modèles Python/EVM | Architecture | Réalisé |
| Provenance complète depuis diagnostic (§3) | Arbre récursif par références | A/E, navigateur, EVM | Architecture | Réalisé |
| Pas de poids, explications ou données sur chaîne (§4) | Métadonnées autorisées, artefacts hors chaîne | Inspection des preuves exportées | Rapport confidentialité | Réalisé |
| Pseudonymes opaques aléatoires (§4) | UUID4 sans identifiant d'entrée | Décisions A/E | Rapport | Réalisé |
| File durable et reprise (§5, §8) | SQLite FULL/WAL, dépendances, backoff 0,5–60 s | Crash, réponse perdue, E | Architecture | Réalisé |
| Pending/submitted/confirmed/failed distincts | Machine d'états outbox | Tests et vue registre | Architecture | Réalisé |
| Agrégation suspendue pendant panne (§3, §9) | Phase contributions persistante | E : trois pending, aucun modèle publié | Démonstration | Réalisé |
| Publication après confirmation (§5, §6) | Mise à jour deployed dans phase model | Panne durable et modèles staged | Architecture | Réalisé |
| Certification avant chaque diagnostic (§6) | Hash des poids chargés, lookup live | C et test outage gate | Rapport certification | Réalisé |
| Substitution entre contrôle et inférence empêchée | Copies NumPy privées, read-only | C, revue du chemin infer | Rapport certification | Réalisé, processus de confiance |
| Diagnostic conservé si ancrage échoue | Objet durable, enveloppe récupérable | `test_pending_decision_after_successful_inference` | Architecture | Réalisé |
| Explication exacte et versionnée (§4, §9) | JSON canonique contributions logit ; téléchargement exact | B, test octets délivrés | CANONICALISATION | Réalisé |
| Vérification modèle et explication (§5) | `verify_model`, `verify_decision`, API | B/C et EVM | README | Réalisé |
| Interface française et arbre réel (§5, §9) | React TS, API provenance | Playwright desktop/mobile | README, captures | Réalisé |
| Statuts, reçus, volumes, raisons, métriques | Tableau, modèle, outbox, provenance | Test navigateur et captures | README | Réalisé |
| Chargement, vide, erreurs, contrôles démo | États UI, contrôles conditionnés par env | Tests auth/demo, navigateur | README | Réalisé |
| Choix technologique argumenté (§7, §11) | Comparaison local/Fabric/Besu/public avant code | ADR versionnée | ADR-001 | Réalisé |
| Progression local puis blockchain (§7) | Deux adaptateurs interchangeables | Tests local puis EVM demo réelle | ADR, README | Réalisé |
| Contrat et configuration (§11) | Solidity, Ganache persistant, config Besu indicative | Tests contrat, transactions RPC | BESU | Réalisé en nœud de développement |
| Déploiement permissionné distribué | Guide de migration, pas de réseau clinique réel | Non exécuté ; organisation/PKI absentes | BESU et rapport | Limité explicitement |
| Cinq scénarios complets (§9) | `scripts.scenarios --scenario A..E` | `reports/scenarios.json` | Démonstration | Réalisé |
| Trois configurations comparées (§10) | Rejeu apparié, trois modes | CSV/JSON bruts, graphique | BENCHMARKS | Réalisé, ablation checkpoint |
| Durée, octets, transactions, croissance (§10) | Chronomètres, payloads, SQLite checkpoint | Benchmarks 3 graines × 2 tailles | BENCHMARKS, rapport | Réalisé localement |
| Reconstruction, falsifications, faux refus (§10) | Essais répétés et panne séparée | Champs CSV et rapport | BENCHMARKS | Réalisé pour cas testés |
| Taille variable à compte fixe (§10) | 6/600 poids, toujours trois contributions | Mesures exportées | BENCHMARKS | Réalisé |
| Rapport, schémas, oral, configuration (§11) | Documents français, Mermaid, exemples sans secrets | Fichiers versionnés | README | Réalisé |
| Limites médicales et confiance (§12) | Notices UI/API/rapport | Inspection notices | Rapport, README | Réalisé |
| Dépendances et commande unique | Manifests/verrous, demo.ps1 | Builds et exécutions documentés | README | Réalisé |

Les extensions de la section 14 (dérive, révocation clinique, double ancrage public, budget formel de confidentialité) restent hors du périmètre. La signature des cliniques, proposée en extension dans le brief, est néanmoins réalisée selon le complément utilisateur. La performance « négligeable » de la section 8 est traitée comme hypothèse à mesurer ; seules les observations du poste sont rapportées.
