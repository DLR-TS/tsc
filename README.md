# TAPAS-SUMO-Coupling (tsc)
Combining traffic demand estimation with microscopic traffic simulation

## Requirements
### Git
Make sure you have git-lfs on your system (`sudo apt-get install git-lfs`) and activated for your user (`git lfs install`).
### Python
The scripts should work with Python 2.7 and Python 3.5 or later. The psycopg2 adapter is needed for database communication.
It is strongly recommended to have the rtree module which speeds up several lookup procedures.
(`sudo apt-get install python-psycopg2 python-rtree` and/or `sudo apt-get install python3-psycopg2 python3-rtree`).
### SUMO
You need to have a working SUMO installation and your environment variable SUMO_HOME needs to be set. On ubuntu
`sudo apt-get install sumo` should suffice.

## Installing
1. Clone this repo `git clone https://github.com/DLR-TS/tsc` (do another pull if you cloned without having lfs active).
2. Run `./install-scenario-templates.py -p data`
