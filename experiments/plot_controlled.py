"""Plot completion rate and median runtime on the common solved subset."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv',type=Path)
    p.add_argument('--output',type=Path,default=Path('results/controlled_plots'))
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    with a.csv.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    groups=defaultdict(list)
    for r in rows: groups[(r['solver'],r['encoding'],r['backend'])].append(r)
    if not groups: raise ValueError('No benchmark rows')
    labels=[' / '.join(v for v in k if v) for k in groups]
    def solved(r): return r['status'] in ('sat','unsat') and r['correct']!='False' and r['assignment_valid']!='False'
    fig,ax=plt.subplots(figsize=(10,5)); ax.bar(labels,[100*sum(map(solved,rs))/len(rs) for rs in groups.values()]); ax.set(ylabel='Completed runs (%)',ylim=(0,100)); ax.tick_params(axis='x',rotation=30); fig.tight_layout(); fig.savefig(a.output/'completion.png',dpi=180); plt.close(fig)
    # A common instance must have all repetitions completed in every configuration.
    per_group=[]
    for rs in groups.values():
        by=defaultdict(list)
        for r in rs: by[r['instance']].append(r)
        per_group.append({i:median(float(r['wall_s']) for r in rr) for i,rr in by.items() if all(map(solved,rr))})
    common=set.intersection(*(set(g) for g in per_group))
    if common:
        fig,ax=plt.subplots(figsize=(10,5)); ax.bar(labels,[median(g[i] for i in common) for g in per_group]); ax.set(ylabel='Median wall time (s)',title=f'Common solved subset: {len(common)} instances'); ax.tick_params(axis='x',rotation=30); fig.tight_layout(); fig.savefig(a.output/'common_runtime.png',dpi=180); plt.close(fig)
    else: print('No common solved instances; runtime comparison omitted.')
    print(a.output)

if __name__=='__main__': main()
