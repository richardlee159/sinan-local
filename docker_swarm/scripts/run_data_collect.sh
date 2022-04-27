cd ../
python3 master_data_collect_ath_social.py --user-name pingheli \
	--stack-name sinan-socialnet \
	--compose-file docker-compose-swarm-single-node.yml \
	--locust-script /mnt/locust/socialml_rps_1.py \
	--min-users 40 --max-users 480 --users-step 20 \
	--exp-time 1200 --measure-interval 1 --slave-port 40011 --deploy-config swarm_ath.json \
	--mab-config social_mab.json --deploy