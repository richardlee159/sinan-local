cd ../
python3 master_deploy_ath_social.py --user-name pingheli \
	--namespace social-network-ml \
	--compose-file social-network-ml-1.json social-network-ml-2.json \
	--min-users 50 --max-users 450 --users-step 50 \
	--exp-time 300 --measure-interval 1 --slave-port 40011 \
	--deploy-config swarm_ath.json \
	--gpu-config gpu.json --gpu-port 40010 \
	--mab-config social_mab.json --deploy