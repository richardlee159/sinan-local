# assume docker version >= 1.13
import sys
import os
import argparse
import logging
from pathlib import Path
import json
import math
# from socket import SOCK_STREAM, socket, AF_INET, SOL_SOCKET, SO_REUSEADDR

from pathlib import Path
sys.path.append(str(Path.cwd()))

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
# parser.add_argument('--cpus', dest='cpus', type=int, required=True)
# parser.add_argument('--stack-name', dest='stack_name', type=str, required=True)
parser.add_argument('--nodes', dest='nodes', nargs='+', type=str, required=True)
parser.add_argument('--cluster-config', dest='cluster_config', type=str, required=True)
parser.add_argument('--replica-cpus', dest='replica_cpus', type=int, default=4)

# data collection parameters
# TODO: add argument parsing here

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# todo: currently assumes all vm instances have the same #cpus
# MaxCpus = args.cpus
# StackName = args.stack_name
nodes = [s.strip() for s in args.nodes]
cluster_config_path = Path.cwd() / '..' / 'config' / args.cluster_config.strip()
replica_cpus = args.replica_cpus
# scale_factor = args.scale_factor
# cpu_percent = args.cpu_percent

IP_ADDR = {}
IP_ADDR["autosys-f12"]     = "172.22.0.14"
IP_ADDR["autosys-f13"]     = "172.22.0.15"
IP_ADDR["autosys-f14"]     = "172.22.0.16"
IP_ADDR["autosys-f15"]     = "172.22.0.17"

service_config = {
    "frontend":          {'max_replica': 1, 'max_cpus': 16},
    "profile":           {'max_replica': 1, 'max_cpus': 8},
    "search":            {'max_replica': 1, 'max_cpus': 8},
    "geo":               {'max_replica': 1, 'max_cpus': 8},
    "rate":              {'max_replica': 1, 'max_cpus': 8},
    "recommendation":    {'max_replica': 1, 'max_cpus': 8},
    "user":              {'max_replica': 1, 'max_cpus': 8},
    "reservation":       {'max_replica': 1, 'max_cpus': 8},
    "memcached-rate":    {'max_replica': 1, 'max_cpus': 8},
    "memcached-profile": {'max_replica': 1, 'max_cpus': 8},
    "memcached-reserve": {'max_replica': 1, 'max_cpus': 8},
    "mongodb-geo":       {'max_replica': 1, 'max_cpus': 8},
    "mongodb-profile":   {'max_replica': 1, 'max_cpus': 8},
    "mongodb-rate":      {'max_replica': 1, 'max_cpus': 8},
    "mongodb-recommendation":   {'max_replica': 1, 'max_cpus': 8},
    "mongodb-reservation":      {'max_replica': 1, 'max_cpus': 8},
    "mongodb-user":      {'max_replica': 1, 'max_cpus': 8}
    # "consul":            {'max_replica': 1, 'max_cpus': 6}
    # "jaeger": {"replica": 1}
}

scalable_service = [
    "frontend",
    "search"
]

for service in service_config:
    service_config[service]['replica'] = service_config[service]['max_replica']
    # service_config[service]['replica_cpus'] = replica_cpus
    if 'max_cpus' not in service_config[service]:
        service_config[service]['max_cpus'] = replica_cpus * service_config[service]['max_replica']
    service_config[service]['cpus'] = service_config[service]['max_cpus']

node_config = {}
for node in nodes:
    assert node in IP_ADDR
    node_config[node] = {}
    node_config[node]['ip_addr'] = IP_ADDR[node]
    if node == 'autosys-f12':
        node_config[node]['cpus'] = 32
        node_config[node]['label'] = 'type=compute'
    else:
        node_config[node]['cpus'] = 32
        node_config[node]['label'] = 'type=data'

cluster_config = {}
cluster_config['nodes'] = node_config
cluster_config['service'] = service_config
cluster_config['scalable_service'] = scalable_service
cluster_config['replica_cpus'] = replica_cpus

with open(str(cluster_config_path), 'w+') as f:
	json.dump(cluster_config, f, indent=4, sort_keys=True)