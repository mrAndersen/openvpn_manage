# openvpn_manage

Manage openvpn connections during day using sqlite3 and /var/log/openvpn/status.log

1. ```git clone this_repo```
2. ```cd this_repo```
3. ```pip install -r requirements.txt```
4. Run script with ./main.py
5. Check if there is valid output
6. Display day results with ./main.py --display
7. Set up cron every minute ro run main.py without parameters
