cd ../
python3 master_data_collect_ath_hotel.py --user-name pingheli \
	--namespace hotel-reservation \
	--compose-file hotel-reservation.json \
	--min-users 200 --max-users 4800 --users-step 100 \
	--exp-time 750 --measure-interval 1 --slave-port 40011 --deploy-config hotel_swarm_ath.json \
	--mab-config hotel_mab.json --deploy