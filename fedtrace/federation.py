"""Clinic worker is a separate interpreter. Only updates cross process boundaries."""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from .canonical import model_hash, metadata
from .identity import identity, sign
from .ledger import body
from .storage import Store

FEATURES = ['inflammation_synthetique', 'auto_anticorps_synthetiques', 'fatigue_synthetique',
            'douleur_synthetique', 'marqueur_synthetique', 'age_standardise_synthetique']


def dataset(seed, count, dimensions, shift=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(shift, 1, (count, dimensions)).astype('float32')
    truth = np.resize(np.array([1.2, -0.8, 0.6, 0.3, -0.4, 0.2]), dimensions)
    logits = x @ truth + rng.normal(0, 0.7, count)
    y = (logits > 0).astype('float32')
    return x, y


def initial(dimensions=6):
    return {'weight': np.zeros(dimensions, dtype='float32'), 'bias': np.zeros(1, dtype='float32')}


def evaluate(weights, seed, count=240):
    x, y = dataset(seed, count, len(weights['weight']))
    logits = np.clip(x @ weights['weight'] + weights['bias'][0], -40, 40)
    p = 1 / (1 + np.exp(-logits))
    return {'accuracy': float(np.mean((p >= .5) == y)),
            'log_loss': float(-np.mean(y*np.log(p+1e-7)+(1-y)*np.log(1-p+1e-7)))}


def aggregate(updates, samples, strategy='robust', threshold=3.0):
    if strategy not in ('fedavg', 'robust') or threshold <= 1:
        raise ValueError('invalid_aggregation')
    vectors = np.stack([np.concatenate([u[k].ravel() for k in sorted(u)]) for u in updates])
    distances = np.linalg.norm(vectors - np.median(vectors, axis=0), axis=1)
    cutoff = max(float(np.median(distances))*threshold, 1e-6)
    accepted = [i for i, d in enumerate(distances) if strategy == 'fedavg' or d <= cutoff]
    if not accepted:
        raise ValueError('no_accepted_contributions')
    total = sum(samples[i] for i in accepted)
    result = {k: sum(updates[i][k].astype('float64')*samples[i]/total for i in accepted).astype(updates[0][k].dtype) for k in updates[0]}
    rejected = {i: 'distance %.6f > seuil %.6f' % (distances[i], cutoff) for i in range(len(updates)) if i not in accepted}
    return result, accepted, rejected


def launch_clinics(home, config, round_id, parent, parent_path):
    store = Store(home)
    request_paths = []
    for i in range(config['clinics']):
        name = 'clinic-%d' % (i+1)
        req = dict(config=config, round=round_id, parent=parent, parent_path=parent_path,
                   clinic=name, index=i, home=str(Path(home).resolve()))
        relative = '%s/r%d/%s-request.json' % (config['experiment'], round_id, name)
        store.write_bytes(relative, metadata(req))
        request_paths.append(store.path(relative))
    def run(path):
        proc = subprocess.run([sys.executable, '-m', 'fedtrace.federation', str(path)], capture_output=True, text=True,
                              env={**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}, timeout=180)
        if proc.returncode:
            raise RuntimeError(proc.stderr)
        return json.loads(proc.stdout)
    with ThreadPoolExecutor(max_workers=config['clinics']) as pool:
        return list(pool.map(run, request_paths))


def worker(request):
    import torch
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    c, i, r = request['config'], request['index'], request['round']
    seed = c['seed'] + i*1000 + r
    torch.manual_seed(seed)
    store = Store(request['home'])
    parent = store.load_model(request['parent_path'])
    count = 96 + i*32
    # Private synthetic clinic partitions: train 60%, validation 20%, test 20%.
    x, y = dataset(c['seed']+i*1000, count, c['dimensions'], (i-(c['clinics']-1)/2)*.45 if c['non_iid'] else 0)
    a, b = int(count*.6), int(count*.8)
    train_x, train_y = torch.from_numpy(x[:a]), torch.from_numpy(y[:a])
    w = torch.tensor(parent['weight'], requires_grad=True)
    bias = torch.tensor(parent['bias'], requires_grad=True)
    optimizer = torch.optim.SGD([w, bias], lr=c['lr'])
    for _ in range(c['epochs']):
        optimizer.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(train_x @ w + bias[0], train_y)
        loss.backward()
        optimizer.step()
    update = {'weight': w.detach().numpy()-parent['weight'], 'bias': bias.detach().numpy()-parent['bias']}
    if c['poison'] and i == c['clinics']-1:
        update = {k: -30*v for k, v in update.items()}
    relative = '%s/r%d/%s-update.npz' % (c['experiment'], r, request['clinic'])
    store.save_model(relative, update)
    # Partitions remain on the same host in this pedagogical prototype, never returned to server.
    local_metrics = {}
    for label, sl in [('validation', slice(a,b)), ('test', slice(b,None))]:
        p = ((x[sl] @ w.detach().numpy() + bias.detach().numpy()[0]) >= 0)
        local_metrics[label+'_accuracy'] = float(np.mean(p == y[sl]))
    record = body('contribution', '%s:r%d:%s' % (c['experiment'],r,request['clinic']), request['clinic'], c['experiment'], r,
                  key='%s:%s' % (c['experiment'],request['clinic']), hash=model_hash(update,'update'), samples=a,
                  parent=request['parent'], privacy={'differential_privacy': False, 'secure_aggregation': False},
                  training={'epochs':c['epochs'], 'lr':c['lr'], 'seed':seed, 'dataset_seed':c['seed']+i*1000,
                            'partition':'60/20/20', 'non_iid':c['non_iid'], 'dimensions':c['dimensions']}, metrics=local_metrics)
    return {'envelope': sign(record, identity(request['home'], request['clinic'])), 'artifact':relative, 'pid':os.getpid()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    args = parser.parse_args()
    print(json.dumps(worker(json.loads(Path(args.request).read_text(encoding='utf-8')))))
