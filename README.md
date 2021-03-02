# TAPAS-SUMO-Coupling (tsc)
Combining traffic demand estimation with microscopic traffic simulation

## Requirements
### Git
Make sure you have git-lfs on your system (`sudo apt-get install git-lfs`) and activated for your user (`git lfs install`).
### Python
The scripts should work with Python 2.7 and Python 3.5 or later. The psycopg2 adapter is needed for database communication.
It is strongly recommended to have the rtree module which speeds up several lookup procedures.
(`sudo apt-get install python-psycopg2 python-rtree` and/or `sudo apt-get install python3-psycopg2 python3-rtree`).
This can also be done using pip (tested with RedHat EL 7) :
`pip install --user wheel rtree psycopg2`
Wheel is needed for rtree installer
### SUMO
You need to have a working SUMO installation and your environment variable SUMO_HOME needs to be set. On ubuntu
`sudo apt-get install sumo` should suffice.

## Installing
1. Clone this repo `git clone https://github.com/DLR-TS/tsc` (do another pull if you cloned without having lfs active).
2. Copy postgres_template.tsccfg (e.g. to postgres.tsccfg) and enter the database connection details (server, user, passwd)
3. Run `./install_scenario_templates.py -c postgres.tsccfg -p data/`

## Running
1. Prepare the credentials file  postgres.tsccfg as described as in section Installing
2. Run `./tsc_main.py -c postgres.tsccfg --daemon` 

The `--daemon`-flag makes tsc loop to look for new sims...

