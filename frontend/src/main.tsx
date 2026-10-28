import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ShieldCheck,
  GitBranch,
  Layers,
  ArrowUpRight,
  RefreshCw,
  Play,
  Search,
  Copy,
  Database,
  FlaskConical,
  AlertTriangle,
} from "lucide-react";
import { stateLabel } from "./states.mjs";
import "./style.css";

type RecordData = {
  body: Record<string, any>;
  receipt: { id: string; confirmed: boolean; adapter: string };
};
type TreeData = { record: RecordData; children: TreeData[] };
type Status = {
  ledger: string;
  adapter: string;
  job: any;
  deployed: any;
  certification: string;
  identities: Record<string, string>;
  records: RecordData[];
  outbox: any[];
  notice: string;
  demo: boolean;
  worker_error: string | null;
};
const Icon = ({ kind }: { kind: string }) =>
  kind === "model" ? (
    <Layers size={18} />
  ) : kind === "decision" ? (
    <ShieldCheck size={18} />
  ) : (
    <Activity size={18} />
  );
function Hash({ value }: { value: string }) {
  return (
    <details className="hash">
      <summary>
        {value.slice(0, 10)}…{value.slice(-6)}
      </summary>
      <code>{value}</code>
      <button
        className="small"
        aria-label="Copier l’empreinte"
        onClick={() => navigator.clipboard.writeText(value)}
      >
        <Copy size={13} /> Copier
      </button>
    </details>
  );
}
function Tree({ node }: { node: TreeData }) {
  const b = node.record.body;
  return (
    <details className="tree" open={b.kind !== "contribution"}>
      <summary>
        <Icon kind={b.kind} />
        <strong>
          {b.kind === "model"
            ? `Modèle · round ${b.round}`
            : b.kind === "decision"
              ? "Décision synthétique"
              : b.actor}
        </strong>
        <span className="muted">
          {b.strategy || b.samples + " échantillons"}
        </span>
      </summary>
      <div className="treebody">
        <Hash value={b.hash} />
        <small>{b.id}</small>
        {b.kind === "model" &&
          Object.entries(b.rejected).map(([id, reason]) => (
            <p className="rejection" key={id}>
              Rejeté : {id} · {String(reason)}
            </p>
          ))}
        {node.children.map((n) => (
          <Tree key={n.record.body.id} node={n} />
        ))}
      </div>
    </details>
  );
}
function App() {
  const [status, setStatus] = useState<Status | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Vue d’ensemble"),
    [busy, setBusy] = useState(false),
    [token, setToken] = useState(""),
    [strategy, setStrategy] = useState("robust"),
    [poison, setPoison] = useState(false),
    [tree, setTree] = useState<TreeData | null>(null),
    [decision, setDecision] = useState<any>(null),
    [verified, setVerified] = useState<any>(null),
    [bench, setBench] = useState<any[]>([]),
    [updated, setUpdated] = useState(""),
    [paused, setPaused] = useState(false);
  async function api(path: string, body?: any) {
    const r = await fetch("/api/" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const result = await r.json();
    if (!r.ok)
      throw Error(result.detail?.reason || JSON.stringify(result.detail));
    return result;
  }
  async function refresh() {
    try {
      setStatus(await api("status"));
      setUpdated(new Date().toLocaleTimeString("fr-FR"));
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    refresh();
    if (!paused) {
      const timer = setInterval(refresh, 4000);
      return () => clearInterval(timer);
    }
  }, [paused]);
  useEffect(() => {
    api("benchmarks")
      .then(setBench)
      .catch((e) => setError(String(e)));
  }, []);
  async function action(fn: () => Promise<any>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const job = status?.job,
    currentRecords =
      status?.records.filter(
        (r) => !job || r.body.experiment === job.config.experiment,
      ) || [],
    models = currentRecords.filter((r) => r.body.kind === "model"),
    contributions = currentRecords.filter(
      (r) => r.body.kind === "contribution",
    ),
    decisions = status?.records.filter((r) => r.body.kind === "decision") || [],
    pending = status?.outbox.filter((o) => o.state !== "confirmed") || [],
    latest = models.at(-1);
  const nav = [
    "Vue d’ensemble",
    "Contributions",
    "Provenance",
    "Simulation",
    "Registre & reprise",
    "Benchmarks",
  ];
  return (
    <div className="app">
      <aside>
        <a className="brand" href="#">
          <span className="brandmark">
            <GitBranch />
          </span>
          FedTrace<span className="version">LAB</span>
        </a>
        <div className="workspace">
          <small>ESPACE DE RECHERCHE</small>
          <strong>Fédération auto-immunité</strong>
          <span>Prototype académique · 2026</span>
        </div>
        <nav aria-label="Navigation principale">
          {nav.map((n, i) => (
            <button
              className={tab === n ? "active" : ""}
              onClick={() => setTab(n)}
              key={n}
            >
              {
                [
                  <Activity />,
                  <Layers />,
                  <GitBranch />,
                  <FlaskConical />,
                  <Database />,
                  <ArrowUpRight />,
                ][i]
              }
              {n}
              {i === 4 && pending.length > 0 && <b>{pending.length}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebarfoot">
          <ShieldCheck size={20} />
          <div>
            <strong>La preuve du processus</strong>
            <p>De la contribution à la décision.</p>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Console d’audit <span className="slash">/</span>{" "}
            <strong>{tab}</strong>
          </span>
          <div className="headerstatus">
            <span
              className={
                "dot " + (status?.ledger === "available" ? "green" : "amber")
              }
            />
            {status ? stateLabel(status.ledger) : "Connexion…"}
            <span className="avatar">AS</span>
          </div>
        </header>
        <div className="content">
          <div className="eyebrow">APPRENTISSAGE FÉDÉRÉ VÉRIFIABLE</div>
          <div className="titlebar">
            <div>
              <h1>
                {tab === "Vue d’ensemble" ? "Une histoire vérifiable." : tab}
              </h1>
              <p className="subtitle">
                Suivez les contributions, certifiez les modèles et remontez
                chaque décision à sa source.
              </p>
            </div>
            <button onClick={() => action(refresh)} disabled={busy}>
              <RefreshCw size={16} /> Actualiser
            </button>
          </div>
          <div className="notice">
            <FlaskConical size={18} />
            <span>
              Simulation pédagogique. Données synthétiques, sans validation
              clinique.
            </span>
            <span className="tag">ENVIRONNEMENT LOCAL</span>
          </div>
          {error && (
            <div className="error" role="alert">
              <AlertTriangle size={18} />
              {error}
              <button onClick={() => setError("")}>Fermer</button>
            </div>
          )}
          {!status ? (
            <div className="panel" role="status">
              Chargement de la fédération…
            </div>
          ) : (
            <>
              {(tab === "Vue d’ensemble" || tab === "Contributions") && (
                <>
                  <div className="stats">
                    <div>
                      <span>Cliniques participantes</span>
                      <strong>
                        {Object.keys(status.identities)
                          .filter((k) => k.startsWith("clinic"))
                          .length.toString()
                          .padStart(2, "0")}
                      </strong>
                      <small>Processus indépendants · même machine</small>
                    </div>
                    <div>
                      <span>Rounds certifiés</span>
                      <strong>
                        {Math.max(0, models.length - 1)
                          .toString()
                          .padStart(2, "0")}
                        <em> / {job?.config.rounds || "—"}</em>
                      </strong>
                      <small>
                        {job?.state === "complete"
                          ? "Expérience terminée"
                          : job
                            ? "Phase : " + job.phase
                            : "Aucune expérience lancée"}
                      </small>
                    </div>
                    <div>
                      <span>Contributions ancrées</span>
                      <strong>
                        {contributions.length.toString().padStart(2, "0")}
                      </strong>
                      <small>{pending.length} ancrage(s) en attente</small>
                    </div>
                    <div>
                      <span>Certification du modèle</span>
                      <strong className="cert">
                        <ShieldCheck size={23} />
                        {stateLabel(status.certification)}
                      </strong>
                      <small>
                        {latest
                          ? "Round " +
                            latest.body.round +
                            " · " +
                            latest.body.strategy
                          : "Lancez une première fédération"}
                      </small>
                    </div>
                  </div>
                  <div className="grid">
                    <section className="panel">
                      <div className="panelhead">
                        <div>
                          <h2>Activité de la fédération</h2>
                          <p>Les preuves précèdent chaque agrégation.</p>
                        </div>
                        <span className="pill">
                          {job?.state === "complete"
                            ? "Terminée"
                            : job
                              ? "En cours"
                              : "Prête"}
                        </span>
                      </div>
                      <div className="pipeline">
                        {[
                          "Entraînement local",
                          "Contributions ancrées",
                          "Agrégation",
                          "Modèle certifié",
                        ].map((n, i) => (
                          <div key={n}>
                            <span
                              className={
                                models.length > 1 ? "step done" : "step"
                              }
                            >
                              {i + 1}
                            </span>
                            <strong>{n}</strong>
                            <small>
                              {
                                [
                                  "Données conservées en clinique",
                                  "Empreintes et signatures",
                                  "Stratégie documentée",
                                  "Porte d’inférence",
                                ][i]
                              }
                            </small>
                          </div>
                        ))}
                      </div>
                      <div className="roundline">
                        <span>Progression des rounds</span>
                        <strong>
                          {Math.max(0, models.length - 1)} /{" "}
                          {job?.config.rounds || 0}
                        </strong>
                      </div>
                      <progress
                        aria-label="Progression des rounds"
                        max={job?.config.rounds || 1}
                        value={Math.max(0, models.length - 1)}
                      />
                      <div className="clinics">
                        {Object.entries(status.identities)
                          .filter(([k]) => k.startsWith("clinic"))
                          .map(([name, address], i) => (
                            <div key={name}>
                              <span className="clinicicon">C{i + 1}</span>
                              <div>
                                <strong>Clinique {i + 1}</strong>
                                <small>
                                  {address.slice(0, 8)}…{address.slice(-5)}
                                </small>
                              </div>
                              <span className="pill">Autorisée</span>
                            </div>
                          ))}
                      </div>
                    </section>
                    <section className="panel modelpanel">
                      <div className="panelhead">
                        <h2>Dernier modèle</h2>
                        <ShieldCheck className="accent" />
                      </div>
                      {latest ? (
                        <>
                          <span className="modelround">
                            ROUND{" "}
                            {latest.body.round.toString().padStart(2, "0")}
                          </span>
                          <h3>
                            {latest.body.strategy === "robust"
                              ? "Agrégation robuste"
                              : latest.body.strategy === "fedavg"
                                ? "Moyenne pondérée"
                                : "Modèle initial"}
                          </h3>
                          <p className="muted">
                            Empreinte SHA-256 des poids canoniques
                          </p>
                          <Hash value={latest.body.hash} />
                          <div className="metric">
                            <span>Exactitude · test synthétique</span>
                            <strong>
                              {latest.body.metrics.test
                                ? (
                                    latest.body.metrics.test.accuracy * 100
                                  ).toFixed(1) + " %"
                                : "—"}
                            </strong>
                          </div>
                          <div className="metric">
                            <span>Contributions retenues / rejetées</span>
                            <strong>
                              {latest.body.accepted.length} /{" "}
                              {Object.keys(latest.body.rejected).length}
                            </strong>
                          </div>
                          <button
                            className="wide"
                            onClick={() =>
                              action(async () => {
                                setTree(
                                  await api("provenance/" + latest.body.id),
                                );
                                setTab("Provenance");
                              })
                            }
                          >
                            Explorer la provenance <ArrowUpRight size={16} />
                          </button>
                        </>
                      ) : (
                        <p className="empty">
                          Aucun modèle certifié. Configurez une expérience
                          ci-dessous.
                        </p>
                      )}
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panelhead">
                      <div>
                        <h2>Contributions & preuves</h2>
                        <p>
                          Chaque mise à jour est signée et ancrée avant son
                          utilisation.
                        </p>
                      </div>
                      <span className="muted">
                        {contributions.length} enregistrements
                      </span>
                    </div>
                    <div className="tablewrap">
                      <table>
                        <thead>
                          <tr>
                            <th>CLINIQUE / ROUND</th>
                            <th>EMPREINTE DE MISE À JOUR</th>
                            <th>ÉCHANTILLONS</th>
                            <th>SORT</th>
                            <th>REÇU</th>
                          </tr>
                        </thead>
                        <tbody>
                          {contributions
                            .slice()
                            .reverse()
                            .map((r) => {
                              const model = models.find(
                                  (m) =>
                                    m.body.round === r.body.round &&
                                    m.body.experiment === r.body.experiment,
                                ),
                                reason = model?.body.rejected[r.body.id];
                              return (
                                <tr key={r.body.id}>
                                  <td>
                                    <strong>{r.body.actor}</strong>
                                    <small>Round {r.body.round}</small>
                                  </td>
                                  <td>
                                    <Hash value={r.body.hash} />
                                  </td>
                                  <td>{r.body.samples}</td>
                                  <td>
                                    <span
                                      className={
                                        "pill " + (reason ? "red" : "")
                                      }
                                    >
                                      {reason
                                        ? "Rejetée"
                                        : model
                                          ? "Retenue"
                                          : "En attente d’agrégation"}
                                    </span>
                                    {reason && (
                                      <small className="rejection">
                                        {reason}
                                      </small>
                                    )}
                                  </td>
                                  <td>
                                    <Hash value={r.receipt.id} />
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                      {!contributions.length && (
                        <p className="empty">
                          Les contributions apparaîtront après le premier
                          entraînement.
                        </p>
                      )}
                    </div>
                  </section>
                </>
              )}
              {tab === "Provenance" && (
                <section className="panel">
                  <div className="panelhead">
                    <div>
                      <h2>De la décision aux cliniques</h2>
                      <p>
                        Historique réel lu depuis le registre, jusqu’au modèle
                        initial.
                      </p>
                    </div>
                  </div>
                  <label>
                    Point de départ
                    <select
                      defaultValue=""
                      onChange={(e) =>
                        e.target.value &&
                        action(async () =>
                          setTree(await api("provenance/" + e.target.value)),
                        )
                      }
                    >
                      <option value="">
                        Choisir un modèle ou une décision
                      </option>
                      {[...decisions, ...models].reverse().map((r) => (
                        <option key={r.body.id} value={r.body.id}>
                          {r.body.kind} · round {r.body.round} · {r.body.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  {tree ? (
                    <Tree node={tree} />
                  ) : (
                    <p className="empty">
                      Sélectionnez un enregistrement pour déplier son
                      historique.
                    </p>
                  )}
                </section>
              )}
              {tab === "Simulation" && (
                <section className="panel">
                  <h2>Soumettre un cas synthétique</h2>
                  <p>
                    Six valeurs standardisées fixes : 0,4 ; −0,3 ; 0,8 ; 0,2 ;
                    −0,1 ; 0,5. La contribution de chaque variable au logit
                    constitue l’explication exacte remise.
                  </p>
                  <button
                    className="primary"
                    disabled={busy || !status.deployed}
                    onClick={() =>
                      action(async () => {
                        setDecision(
                          await api("diagnose", {
                            features: [0.4, -0.3, 0.8, 0.2, -0.1, 0.5],
                          }),
                        );
                        setVerified(null);
                      })
                    }
                  >
                    <FlaskConical size={17} /> Exécuter la simulation
                  </button>
                  {decision && (
                    <div className="result">
                      <h3>
                        Probabilité synthétique :{" "}
                        {(decision.probability * 100).toFixed(2)} %
                      </h3>
                      <span className="pill">{stateLabel(decision.state)}</span>
                      <Hash value={decision.hash} />
                      <pre>{JSON.stringify(decision.explanation, null, 2)}</pre>
                      <a
                        className="download"
                        href={"/api/decisions/" + decision.id + "/explanation"}
                      >
                        Télécharger les octets exacts de l’explication
                      </a>
                      <button
                        onClick={() =>
                          action(async () =>
                            setVerified(
                              await api("decisions/" + decision.id + "/verify"),
                            ),
                          )
                        }
                      >
                        <Search size={16} /> Vérifier l’explication
                      </button>
                      <button
                        onClick={() =>
                          action(async () => {
                            setTree(await api("provenance/" + decision.id));
                            setTab("Provenance");
                          })
                        }
                      >
                        Reconstituer la provenance
                      </button>
                      {verified && (
                        <p role="status">
                          Intégrité : {stateLabel(verified.state)}
                        </p>
                      )}
                    </div>
                  )}
                </section>
              )}
              {tab === "Registre & reprise" && (
                <section className="panel">
                  <h2>{status.adapter}</h2>
                  <p>
                    Reprise automatique chaque seconde ; délai exponentiel borné
                    à 60 secondes. Un ancrage soumis reste non certifié jusqu’à
                    confirmation.
                  </p>
                  {status.demo && (
                    <div className="controls">
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(() => api("demo/ledger/offline", {}))
                        }
                      >
                        Simuler l’indisponibilité
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(() => api("demo/ledger/online", {}))
                        }
                      >
                        Rétablir le registre
                      </button>
                    </div>
                  )}
                  <div className="tablewrap">
                    <table>
                      <thead>
                        <tr>
                          <th>IDENTIFIANT</th>
                          <th>ÉTAT</th>
                          <th>ESSAIS</th>
                          <th>ERREUR</th>
                        </tr>
                      </thead>
                      <tbody>
                        {status.outbox.map((o) => (
                          <tr key={o.id}>
                            <td className="wrap">{o.id}</td>
                            <td>{stateLabel(o.state)}</td>
                            <td>{o.attempts}</td>
                            <td>{o.error || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {status.worker_error && (
                    <pre className="error">{status.worker_error}</pre>
                  )}
                </section>
              )}
              {tab === "Benchmarks" && (
                <section className="panel">
                  <h2>Mesures reproductibles</h2>
                  <p>
                    Mesures locales exportées depuis les exécutions réelles. Les
                    durées incluent le lancement des processus cliniques.
                  </p>
                  {!bench.length ? (
                    <p className="empty">
                      Exécutez python -m scripts.benchmark pour générer les
                      mesures.
                    </p>
                  ) : (
                    <div className="tablewrap">
                      <table>
                        <thead>
                          <tr>
                            <th>CONFIGURATION</th>
                            <th>DIMENSIONS</th>
                            <th>N</th>
                            <th>DURÉE MOYENNE (s)</th>
                            <th>ÉCART-TYPE (s)</th>
                            <th>TRANSACTIONS / ROUND</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bench.map((b, i) => (
                            <tr key={i}>
                              <td>{b.mode}</td>
                              <td>{b.dimensions}</td>
                              <td>{b.n}</td>
                              <td>{b.mean_seconds.toFixed(3)}</td>
                              <td>{b.std_seconds.toFixed(3)}</td>
                              <td>{b.transactions_per_round}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              )}
              <section className="panel configuration">
                <div>
                  <h2>Lancer une expérience</h2>
                  <p>3 cliniques · 3 rounds · 6 époques · graine 42</p>
                </div>
                <label>
                  Stratégie
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value)}
                  >
                    <option value="robust">
                      Filtre robuste + moyenne pondérée
                    </option>
                    <option value="fedavg">FedAvg pondéré</option>
                  </select>
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={poison}
                    onChange={(e) => setPoison(e.target.checked)}
                  />{" "}
                  Empoisonner la clinique 3
                </label>
                <button
                  className="primary"
                  disabled={busy || !!(job && job.state !== "complete")}
                  onClick={() =>
                    action(() => api("experiments", { strategy, poison }))
                  }
                >
                  <Play size={16} />
                  {busy ? "Traitement…" : "Lancer la fédération"}
                </button>
              </section>
              <details className="credentials">
                <summary>Authentification locale des actions</summary>
                <label>
                  Jeton du dépositaire local
                  <input
                    type="password"
                    value={token}
                    autoComplete="off"
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="Jeton affiché par la commande serve"
                  />
                </label>
                <p>
                  Ce prototype conserve les clés des cliniques sur le même
                  poste. Le jeton permet les actions administratives et les
                  décisions de la clinique 1.
                </p>
              </details>
            </>
          )}
          <footer>
            <span>
              FedTrace · Traçabilité du processus, sans garantie de qualité
              clinique.
            </span>
            <span>
              {updated && "Relevé à " + updated}{" "}
              <button className="small" onClick={() => setPaused(!paused)}>
                {paused ? "Reprendre" : "Suspendre"} l’actualisation
              </button>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
