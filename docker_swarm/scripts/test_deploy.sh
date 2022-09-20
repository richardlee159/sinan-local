cd ../
python3 master_deploy_ath_social.py --user-name pingheli \
	--namespace social-network-ml \
	--compose-file social-network-ml-1.json social-network-ml-2.json \
	--trace-dir /home/pingheli/traces-rps/socialml \
	--measure-interval 1 --slave-port 40011 \
	--cnn-valid-err 50 \
	--xgb-scale-down-threshold 0.15 --xgb-scale-up-threshold 0.3 \
	--deploy-config swarm_ath.json \
	--gpu-config gpu.json --gpu-port 40010 \
	--mab-config social_mab.json --deploy