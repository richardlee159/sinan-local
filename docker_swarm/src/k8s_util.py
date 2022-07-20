import os
import sys
import subprocess
import logging
import time

from pathlib import Path
sys.path.append(str(Path.cwd()))

def stat_path(stat, uid, qos='besteffort'):
    family, _, name = stat.partition('.')
    slices = f'kubepods.slice/kubepods-{qos}.slice/kubepods-{qos}-pod{uid.replace("-", "_")}.slice'
    return Path(f'/sys/fs/cgroup/{family}/{slices}/{family}.{name}')

def set_cpu_limit(uid, limit, period=0.1):
    period_us = round(period * 1e6)
    assert 1000 <= period_us <= 1000000
    if limit is None:
        quota_us = -1
    else:
        quota_us = round(limit * period_us)
        assert quota_us >= 1000
    stat_path('cpu.cfs_period_us', uid).write_text(str(period_us))
    stat_path('cpu.cfs_quota_us', uid).write_text(str(quota_us))

def kubectl_delete(path, namespace):
    subprocess.run(['kubectl', 'delete', '-f', path],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    while True:
        p = subprocess.run(['kubectl', 'get', 'pods', f'-n={namespace}',
            r'-o=jsonpath={range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
        if p.stdout == '':
            return
        time.sleep(1)

def kubectl_apply(path, namespace, pod_count):
    def all_ready(output):
        l = output.splitlines()
        if len(l) != pod_count:
            return False
        for i in l:
            name, phase = i.split()
            if phase == 'Running':
                continue
            if phase == 'Succeeded':
                if name.startswith('jaeger-cassandra-schema-'):
                    continue
            return False
        return True

    subprocess.run(['kubectl', 'apply', '-f', path],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True)
    logging.info('wait for services to converge')
    while True:
        p = subprocess.run(['kubectl', 'get', 'pods', f'-n={namespace}',
            r'-o=jsonpath={range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
        if all_ready(p.stdout):
            logging.info('services converged')
            return
        time.sleep(1)

def k8s_deploy(benchmark_dir, compose_file, namespace, pod_count):
    kubectl_delete(str(compose_file), namespace)
    time.sleep(5)
    kubectl_apply(str(compose_file), namespace, pod_count)
    time.sleep(5)

    # set up social network topoloy and post storage
    if 'social' in namespace:
        cmd = 'python3 ' + str(benchmark_dir / 'scripts' / 'init_social_graph.py') + ' --port 30001 --compose' + \
             ' --graph ' + str(benchmark_dir / 'datasets' / 'social-graph' / 'socfb-Reed98' / 'socfb-Reed98.mtx')
        subprocess.call(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr, preexec_fn=os.setsid,bufsize=-1)
        # print 'setup_social_graph_init_data.py out: ', out
        logging.info('social network set up done')
        time.sleep(30)
    
    return True
