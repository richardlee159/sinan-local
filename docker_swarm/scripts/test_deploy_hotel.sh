cd ../
python3 master_deploy_ath_hotel.py --user-name pingheli \
	--namespace hotel-reservation \
	--compose-file hotel-reservation.json \
	--min-users 1000 --max-users 4000 --users-step 300 \
	--exp-time 300 --measure-interval 1 --slave-port 40011 \
	--deploy-config hotel_swarm_ath.json \
	--gpu-config hotel_gpu.json --gpu-port 40010 \
	--mab-config hotel_mab.json --deploy