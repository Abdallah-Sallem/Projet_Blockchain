# Passage à un consortium Besu

Le contrat est compatible EVM Shanghai et peut être porté sur Besu ; le déploiement **effectivement testé** utilise Ganache sur un seul nœud. La présence de Docker ne fournit pas les organisations, la PKI, les clés et la gouvernance d'un consortium. Aucune résistance byzantine ni exploitation hospitalière distribuée n'a été validée.

Pour construire un réseau Besu QBFT de laboratoire, employer le tutoriel officiel [QBFT](https://besu.hyperledger.org/private-networks/tutorials/qbft) et un réseau isolé avec quatre validateurs, des clés différentes, un genesis commun et les ports P2P/RPC autorisés. La configuration fournie ci-dessous est un **point de départ à adapter**, pas un réseau distribué exécuté ici. Le code utilise un client HTTP standard et n'exige pas de logique spécifique Ganache.

```powershell
# Après installation et génération du genesis et des clés selon le tutoriel Besu :
besu --data-path=network/Node-1/data --genesis-file=network/genesis.json --network-id=1337 --rpc-http-enabled --rpc-http-host=127.0.0.1 --rpc-http-port=8545 --rpc-http-api=ETH,NET,WEB3 --host-allowlist=localhost,127.0.0.1 --min-gas-price=0
# Démarrer Node-2 à Node-4 avec leurs clés, ports et bootnodes propres.
```

Fichier `contracts/besu-config.toml` : exemple RPC local, à combiner avec les chemins et bootnodes de chaque nœud. Pour déployer sur Besu, **ne pas utiliser scripts.deploy**, qui finance une clé via un compte déverrouillé de développement. Compiler avec `npm run compile`, financer une clé de passerelle de laboratoire dans le genesis, construire et signer la transaction de déploiement avec cette clé, puis renseigner FEDTRACE_RPC, FEDTRACE_CONTRACT et FEDTRACE_EVM_KEY. Le guide officiel [web3.py transactions](https://web3py.readthedocs.io/en/stable/transactions.html) décrit la construction et la signature hors ligne utilisées aussi dans `fedtrace/evm.py`.

Travail restant pour une véritable fédération indépendante : répartition des clés et autorités, permissionnement comptes/nœuds, politiques de révocation, déploiement signé, authentification et TLS RPC, sauvegardes, finalité/reorgs explicites et tests de perte de validateurs. L'adaptateur de développement considère un reçu miné réussi comme confirmé ; il ne gère pas de profondeur de finalité sur chaîne publique.
