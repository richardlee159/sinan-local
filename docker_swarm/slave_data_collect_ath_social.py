# Docker version 19.03.11, Ubuntu 18.04
import sys
import os
import socket
import subprocess
import threading
import time
import json
import argparse
import logging
from pathlib import Path
import copy
sys.path.append(str(Path.cwd() / 'src'))
import k8s_util

# slave is responsible for adjusting resources on each server
# collecting per-server information, including cpu, network & memory
# assume each vm can hold multiple pods

# -----------------------------------------------------------------------
# parser args definition
# -----------------------------------------------------------------------
parser = argparse.ArgumentParser()
# parser.add_argument('--instance-name', dest='instance_name', type=str, required=True)
parser.add_argument('--cpus', dest='cpus', type=int, required=True)
# parser.add_argument('--max-memory', dest='max_memory',type=str, required=True)	# in MB
parser.add_argument('--server-port', dest='server_port',type=int, default=40011)
parser.add_argument('--service-config', dest='service_config', type=str, required=True)
parser.add_argument('--namespace', dest='namespace', type=str, required=True)

# -----------------------------------------------------------------------
# parse args
# -----------------------------------------------------------------------
args = parser.parse_args()
# global variables
Cpus 	 = args.cpus
Namespace = args.namespace
# MaxMemory 	 = args.max_memory
ServerPort   = args.server_port
MsgBuffer    = ''

Services = []
ServiceConfig = {}
# services deployed on the server
with open(args.service_config, 'r') as f:
	Services 	= json.load(f)['services']
	ServiceConfig = {}
	for s in Services:
		ServiceConfig[s] = {}
		ServiceConfig[s]['cpus'] = 0

Pods  = {}	# indexed by service name
PodList = []	# a list of all pod names
PodStats = {}	# indexed by pod names
ServiceReplicaUpdated = []	# services whose replica is just updated

# logging.basicConfig(level=logging.INFO,
#                     format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def clear_pod_stats():
	global Pods
	global PodList
	global PodStats
	Pods = {}
	PodList = []
	PodStats = {}

def create_pod_stats(service, pod_name, pod_id):
	global Pods
	global PodList
	global PodStats

	logging.info("Create stats for pod %s of %s" %(pod_name, service))
	assert service in pod_name # make sure service matches pod_name
	if service not in Pods:
		Pods[service] = []
	assert pod_name not in Pods[service]
	assert pod_name not in PodStats
	assert pod_name not in PodList
	Pods[service].append(pod_name)
	PodList.append(pod_name)
	PodStats[pod_name] = {}
	PodStats[pod_name]['id']   = pod_id
	# variables below are cummulative
	PodStats[pod_name]['rx_packets'] = 0
	PodStats[pod_name]['rx_bytes'] = 0
	PodStats[pod_name]['tx_packets'] = 0
	PodStats[pod_name]['tx_bytes'] = 0
	PodStats[pod_name]['page_faults'] = 0
	PodStats[pod_name]['cpu_time'] = 0
	PodStats[pod_name]['io_bytes'] = 0
	PodStats[pod_name]['io_serviced'] = 0

# used when previous pod failed and a new one is rebooted
def reset_pod_ids():
	logging.info('reset_pod_ids')
	clear_pod_stats()
	kubectl_get_pods()

def kubectl_get_pods():
	global Services
	global Namespace

	p = subprocess.run(['kubectl', 'get', 'pods', f'-n={Namespace}',
		f'--field-selector=spec.nodeName={socket.gethostname()}',
		r'-o=jsonpath={range .items[*]}{.metadata.uid} {.metadata.name}{"\n"}{end}'],
		stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
	for i in p.stdout.splitlines():
		pod_id, pod_name = i.split()
		service = pod_name.rsplit('-', 2)[0]
		if service not in Services:
			continue

		logging.info("kubectl get pods name = %s, id = %s service = %s" %(pod_name, pod_id, service))
		create_pod_stats(service, pod_name, pod_id)

def remove_stale_pods(service, updated_pods):
	global Pods
	global PodList
	global PodStats

	if service in Pods:
		stale_pods = [c for c in Pods[service] if c not in updated_pods]
	else:
		stale_pods = []
	Pods[service] = list(updated_pods)
	for c in stale_pods:
		del PodStats[c]
	PodList = [c for c in PodList if c not in stale_pods]

# used when replica of a service is updated
def update_replica(updated_service_list):
	global Pods
	global PodList
	global PodStats
	global ServiceReplicaUpdated

	# todo: update Pod[service] & PodList & PodStats
	# delete records of removed pods

	new_pod_names = []
	updated_pods = {}	# indexed by service
	p = subprocess.run(['kubectl', 'get', 'pods', f'-n={Namespace}',
		f'--field-selector=spec.nodeName={socket.gethostname()}',
		r'-o=jsonpath={range .items[*]}{.metadata.uid} {.metadata.name}{"\n"}{end}'],
		stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
	for i in p.stdout.splitlines():
		pod_id, pod_name = i.split()
		service = pod_name.rsplit('-', 2)[0]
		if service not in Services:
			continue
		if service not in updated_service_list:
			continue
		if service not in updated_pods:
			updated_pods[service] = []
		assert pod_name not in updated_pods[service]
		updated_pods[service].append(pod_name)
		# no need to create record for previously existing pod
		if service in Pods and pod_name in Pods[service]:
			continue
		if service not in ServiceReplicaUpdated:
			ServiceReplicaUpdated.append(service)
		assert pod_name not in new_pod_names
		new_pod_names.append(pod_name)
		logging.info("kubectl get pods name = %s, id = %s service = %s" %(pod_name, pod_id, service))
		create_pod_stats(service, pod_name, pod_id)

	for service in updated_pods:
		remove_stale_pods(service, updated_pods[service])

def compute_mean(stat_dict):
	global Pods

	return_state_dict = {}
	for service in Pods:
		s = 0
		for c in Pods[service]:
			assert c in stat_dict
			s += stat_dict[c]
		return_state_dict[service] = float(s)/len(Pods[service])

	return return_state_dict

def compute_sum(stat_dict):
	global Pods

	return_state_dict = {}
	for service in Pods:	# only count existing services
		s = 0
		for c in Pods[service]:
			assert c in stat_dict
			s += stat_dict[c]
		return_state_dict[service] = s

	return return_state_dict

def compute_max(stat_dict):
	global Pods

	return_state_dict = {}
	for service in Pods:	# only count existing services
		s = 0
		for c in Pods[service]:
			assert c in stat_dict
			s = max(s, stat_dict[c])
		return_state_dict[service] = s

	return return_state_dict

def concatenate(stat_dict):
	global Pods

	return_state_dict = {}
	for service in Pods:	# only count existing services
		return_state_dict[service] = []
		for c in Pods[service]:
			assert c in stat_dict
			return_state_dict[service].append(stat_dict[c])

	return return_state_dict

def get_replica():
	global Services
	global Pods

	replica_dict = {}
	for service in Services:
		if service not in Pods:
			replica_dict[service] = 0
		else:
			replica_dict[service] = len(Pods[service])
	return replica_dict

# Inter-|   Receive                                                |  Transmit
#  face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
#     lo:       0       0    0    0    0     0          0         0        0       0    0    0    0     0       0          0
#   eth0: 49916697477 44028473    0    0    0     0          0         0 84480565155 54746827    0    0    0     0       0          0

def get_network_usage():
	global Pods
	global PodList
	global PodStats

	rx_packets = {}
	rx_bytes   = {}
	tx_packets = {}
	tx_bytes   = {}

	ret_rx_packets = {}
	ret_rx_bytes   = {}
	ret_tx_packets = {}
	ret_tx_bytes   = {}

	while True:
		fail = False
		for pod in PodList:
			rx_packets[pod] = 0
			rx_bytes[pod]   = 0
			tx_packets[pod] = 0
			tx_bytes[pod]   = 0

			if fail:
				break
			ret_rx_packets[pod] = rx_packets[pod] - PodStats[pod]['rx_packets']
			ret_rx_bytes[pod]   = rx_bytes[pod]	- PodStats[pod]['rx_bytes']
			ret_tx_packets[pod] = tx_packets[pod] - PodStats[pod]['tx_packets']
			ret_tx_bytes[pod]   = tx_bytes[pod]	- PodStats[pod]['tx_bytes']

			if ret_rx_packets[pod] < 0:
				ret_rx_packets[pod] = rx_packets[pod]
			if ret_rx_bytes[pod] < 0:
				ret_rx_bytes[pod] = rx_bytes[pod]
			if ret_tx_packets[pod] < 0:
				ret_tx_packets[pod] = tx_packets[pod]
			if ret_tx_bytes[pod] < 0:
				ret_tx_bytes[pod] = tx_bytes[pod]

			PodStats[pod]['rx_packets'] = rx_packets[pod]
			PodStats[pod]['rx_bytes']   = rx_bytes[pod]
			PodStats[pod]['tx_packets'] = tx_packets[pod]
			PodStats[pod]['tx_bytes']   = tx_bytes[pod]

		if not fail:
			break

		else:
			reset_pod_ids()

	# return compute_mean(ret_rx_packets), compute_mean(ret_rx_bytes), compute_mean(ret_tx_packets), compute_mean(ret_tx_bytes)
	# return compute_sum(ret_rx_packets), compute_sum(ret_rx_bytes), compute_sum(ret_tx_packets), compute_sum(ret_tx_bytes) 
	return concatenate(ret_rx_packets), concatenate(ret_rx_bytes), concatenate(ret_tx_packets), concatenate(ret_tx_bytes)

def get_memory_usage():
	global Pods
	global PodList
	global PodStats

	rss = {}	# resident set size, memory belonging to process, including heap & stack ...
	cache_memory = {}	# data stored on disk (like files) currently cached in memory
	page_faults  = {}

	for pod in PodList:
		pseudo_file = k8s_util.stat_path('memory.stat', PodStats[pod]["id"])
		with open(str(pseudo_file), 'r') as f:
			lines = f.readlines()
			for line in lines:
				if 'total_cache' in line:
					cache_memory[pod] = round(int(line.split(' ')[1])/(1024.0**2), 3)	# turn byte to mb
				elif 'total_rss' in line and 'total_rss_huge' not in line:
					rss[pod] = round(int(line.split(' ')[1])/(1024.0**2), 3)
				elif 'total_pgfault' in line:
					pf = int(line.split(' ')[1])
					page_faults[pod] = pf - PodStats[pod]['page_faults']
					if page_faults[pod] < 0:
						page_faults[pod] = pf
					PodStats[pod]['page_faults'] = pf

		assert rss[pod] >= 0
		assert cache_memory[pod] >= 0
		assert page_faults[pod] >= 0

	# return compute_mean(rss), compute_mean(cache_memory), compute_mean(page_faults)
	# return compute_sum(rss), compute_sum(cache_memory), compute_sum(page_faults)
	return concatenate(rss), concatenate(cache_memory), concatenate(page_faults)

# cpu time percentages used on behalf on the pod
# mpstat gets information of total cpu usage including colated workloads
def get_docker_cpu_usage():
	global Pods
	global PodList
	global PodStats

	docker_cpu_time = {}
	while True:
		fail = False
		for pod in PodList:
			pseudo_file = k8s_util.stat_path('cpuacct.usage', PodStats[pod]["id"])
			if not pseudo_file.is_file():
				fail = True
				break
			with open(str(pseudo_file), 'r') as f:
				cum_cpu_time = int(f.readlines()[0])/1000000.0	# turn ns to ms
			docker_cpu_time[pod] = max(cum_cpu_time - PodStats[pod]['cpu_time'], 0)
			PodStats[pod]['cpu_time'] = cum_cpu_time

		if not fail:
			break
		else:
			reset_pod_ids()

	return concatenate(docker_cpu_time)

def get_io_usage():
	global Pods
	global PodList
	global PodStats

	ret_io_bytes	= {}
	ret_io_serviced = {}

	for pod in PodList:	
		# io sectors (512 bytes)
		pseudo_file = k8s_util.stat_path('blkio.throttle.io_service_bytes_recursive', PodStats[pod]["id"])
		with open(str(pseudo_file), 'r') as f:
			lines = f.readlines()
			if len(lines) > 0:
				sector_num = int(lines[0].split(' ')[-1])
				ret_io_bytes[pod] = sector_num - PodStats[pod]['io_bytes']
				if ret_io_bytes[pod] < 0:
					ret_io_bytes[pod] = sector_num
			else:
				sector_num = 0
				ret_io_bytes[pod] = 0

			PodStats[pod]['io_bytes'] = sector_num

		# io services
		pseudo_file = k8s_util.stat_path('blkio.throttle.io_serviced_recursive', PodStats[pod]["id"])
		with open(str(pseudo_file), 'r') as f:
			lines = f.readlines()
			for line in lines:
				if 'Total' in line:
					serv_num = int(line.split(' ')[-1])
					ret_io_serviced[pod] = serv_num - PodStats[pod]['io_serviced']
					if ret_io_serviced[pod] < 0:
						ret_io_serviced[pod] = serv_num
					PodStats[pod]['io_serviced'] = serv_num

		assert pod in ret_io_bytes
		assert pod in ret_io_serviced

	# return compute_mean(ret_io_bytes), compute_mean(ret_io_serviced), compute_mean(ret_io_wait)
	# return compute_sum(ret_io_bytes), compute_sum(ret_io_serviced), compute_sum(ret_io_wait)
	return concatenate(ret_io_bytes), concatenate(ret_io_serviced)

# run before each experiment
# TODO: reimplement
# @service_restart: set to true if entire application is restarted
def init_data():
	global Services
	global ServiceConfig
	# reset pod id every time, since we can't control placement with k8s
	reset_pod_ids()

	# read initial values
	get_docker_cpu_usage()
	get_memory_usage()
	get_network_usage()
	get_io_usage()

# cpu cycle limit
def set_cpu_limit(cpu_config, quiet=False):
	global Services
	global ServiceConfig
	global Pods
	global Cpus
	global ServiceReplicaUpdated

	_stdout = sys.stdout
	_stderr = sys.stderr
	if quiet:
		_stdout = subprocess.DEVNULL
		_stderr = subprocess.DEVNULL

	for service in Services:
		assert service in cpu_config
		assert 'cpus' in cpu_config[service]
		if ServiceConfig[service]['cpus'] == cpu_config[service]['cpus'] and \
			service not in ServiceReplicaUpdated:
			continue
		if service not in Pods:
			continue

		if cpu_config[service]['cpus'] == 0:
			per_pod_cpu = Cpus
		else:
			assert cpu_config[service]['cpus'] <= Cpus
			per_pod_cpu = float(cpu_config[service]['cpus'])	# cpus field here directly refers to per pod cpu
		ServiceConfig[service]['cpus'] = cpu_config[service]['cpus']	
	
		for pod in Pods[service]:
			k8s_util.set_cpu_limit(PodStats[pod]['id'], per_pod_cpu)

	ServiceReplicaUpdated = []	# clear replica update history

#--------- Resources not yet implemented -----------#
def set_freq(freq_config, quiet=False):
	pass

# physical cores
def set_core(core_config, quiet=False):
	# docker update --cpuset-cpus=29,31,33,35 gomicroserviceszipkinsample_rate_1
	pass

# return list of cores allocated for service
def allocate_core(service, core_config):
	return []
#---------------------------------------------------#

# TODO: experiment writing net fs or sending through network
def start_experiment(host_sock):
	global MsgBuffer
	global Services
	global ServiceConfig

	logging.info('experiment starts')
	prev_host_query_time = time.time()
	terminate = False

	exp_succ = True
	while True:
		data = host_sock.recv(1024).decode('utf-8')
		# print 'recv: ', data
		MsgBuffer += data

		if len(data) == 0:
			logging.error('host_sock reset during experiment')
			terminate = True
			exp_succ = False

		while '\n' in MsgBuffer:
			(cmd, rest) = MsgBuffer.split('\n', 1)
			MsgBuffer = rest

			logging.info('cmd: ' + cmd)

			if 'get_info' in cmd:
				cur_time = time.time()
				logging.info('time since last host query: ' + format(cur_time - prev_host_query_time, '.2f') + 's')
				replica_dict = get_replica()
				docker_cpu_time = get_docker_cpu_usage()
				rss, cache_memory, page_faults = get_memory_usage()
				rx_packets, rx_bytes, tx_packets, tx_bytes = get_network_usage()
				io_bytes, io_serviced = get_io_usage()

				ret_info = {}
				elapsed_time = (cur_time - prev_host_query_time)*1000	# in ms
				for service in Pods:
					ret_info[service] = {}
					ret_info[service]['replica']	 = replica_dict[service]
					# turn to virtual cpu number
					# ret_info[service]['cpu_docker']  = round(docker_cpu_time[service]/((cur_time - prev_host_query_time)*1000), 4)
					ret_info[service]['cpu_docker']  = [ round(c/elapsed_time, 4) for c in docker_cpu_time[service] ]
					ret_info[service]['rss'] 		 = rss[service]
					ret_info[service]['cache_mem']   = cache_memory[service]
					ret_info[service]['pgfault'] 	 = page_faults[service]
					ret_info[service]['rx_pkt'] 	 = rx_packets[service]
					ret_info[service]['rx_byte'] 	 = rx_bytes[service]
					ret_info[service]['tx_pkt'] 	 = tx_packets[service]
					ret_info[service]['tx_byte'] 	 = tx_bytes[service]
					ret_info[service]['io_bytes'] 	 = io_bytes[service]
					ret_info[service]['io_serv'] 	 = io_serviced[service]

				prev_host_query_time = cur_time
				ret_msg = json.dumps(ret_info) + '\n'
				host_sock.sendall(ret_msg.encode('utf-8'))

			elif 'set_rsc' in cmd:
				cpu_config = json.loads(cmd.split('----')[-1])
				set_cpu_limit(cpu_config, quiet=True)

			elif 'update_replica' in cmd:
				updated_service_list = json.loads(cmd.split('----')[-1])
				update_replica(updated_service_list)
				host_sock.sendall(('update_replica_done\n').encode('utf-8'))

			elif 'terminate_exp' in cmd:
				# host_sock.sendall('experiment_done\n')
				terminate = True

			elif len(cmd) == 0:
				continue

			else:
				logging.error('Error: undefined cmd: ' + cmd)
				exp_succ = False
				terminate = True

		if terminate:
			host_sock.sendall(('experiment_done\n').encode('utf-8'))
			return exp_succ

def main():
	global ServerPort
	global MsgBuffer
	global Services

	local_serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	local_serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	#---------------------------------
	# When application / server is configured for localhost or 127.0.0.1, 
	# which means accept connections only on the local machine. 
	# You need to bind with 0.0.0.0 which means listen on all available networks.
	#------------------------------------
	local_serv_sock.bind(('0.0.0.0', ServerPort))
	local_serv_sock.listen(1024)
	host_sock, addr = local_serv_sock.accept()
	host_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

	MsgBuffer = ''
	terminate = False
	while True:
		data = host_sock.recv(1024).decode('utf-8')
		if len(data) == 0:
			logging.warning('connection reset by host, exiting...')
			break

		MsgBuffer += data
		while '\n' in MsgBuffer:
			(cmd, rest) = MsgBuffer.split('\n', 1)
			MsgBuffer = rest
			logging.info('cmd = ' + cmd)

			if 'init_data' in cmd:
				init_data()
				host_sock.sendall(('init_data_done\n').encode('utf-8'))
			elif 'exp_start' in cmd:
				assert '\n' not in rest
				# docker_restart = (int(cmd.split(' ')[2]) == 1)
				stat = start_experiment(host_sock)
				if not stat:	# experiment failed
					terminate = True
					break
				if len(MsgBuffer) > 0:
					logging.info('Cmds left in MsgBuffer (after exp complete): ' + MsgBuffer)
					MsgBuffer = ''
			elif 'terminate_slave' in cmd:
				terminate = True
				break

		if terminate:
			break

if __name__ == '__main__':
	# reload_sched_states()
	main()