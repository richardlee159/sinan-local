cd ../
python3 master_deploy_diurnal_ath_social.py --user-name pingheli \
	--stack-name sinan-socialnet \
	--compose-file docker-compose-swarm-single-node.yml \
	--locust-script /mnt/locust/socialml_rps_1.py \
	--min-users 40 --max-users 360 --users-step 40 \
	--exp-time 120 --measure-interval 1 --slave-port 40011 \
	--deploy-config swarm_ath.json \
	--gpu-config gpu.json --gpu-port 40010 \
	--mab-config social_mab.json