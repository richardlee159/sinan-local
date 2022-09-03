cd ../
python3 master_deploy_ath_hotel.py --user-name pingheli \
	--namespace hotel-reservation \
	--compose-file hotel-reservation.json \
	--trace-dir /home/pingheli/traces-rps/hotel \
	--measure-interval 1 --slave-port 40011 \
	--cnn-valid-err 45 \
	--xgb-scale-down-threshold 0.15 --xgb-scale-up-threshold 0.3 \
	--deploy-config hotel_swarm_ath.json \
	--gpu-config hotel_gpu.json --gpu-port 40010 \
	--mab-config hotel_mab.json --deploy