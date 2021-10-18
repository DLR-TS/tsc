# TAPAS-SUMO-Coupling (tsc)
Combining traffic demand estimation with microscopic traffic simulation

## Requirements
### Git
Make sure you have git-lfs on your system (`sudo apt-get install git-lfs`) and activated for your user (`git lfs install`).

### Python
The scripts should work with Python 2.7 and Python 3.5 or later. The psycopg2 adapter is needed for database communication.
It is strongly recommended to have the rtree module which speeds up several lookup procedures and pandas
if you need GTFS import.
(`sudo apt-get install python-psycopg2 python-rtree python-pandas` and/or `sudo apt-get install python3-psycopg2 python3-rtree python3-pandas`).
This can also be done using pip (tested with RedHat EL 7):
`pip install --user wheel -r requirements.txt`
Wheel is needed for rtree installer

### SUMO
You need to have a working SUMO installation and your environment variable SUMO_HOME needs to be set. On ubuntu
`sudo apt-get install sumo` should suffice.

## Installing
1. Clone this repo `git clone https://github.com/DLR-TS/tsc` (do another pull if you cloned without having lfs active).
2. Copy postgres_template.tsccfg (e.g. to postgres.tsccfg) and enter the database connection details (server, user, passwd)
3. Run `./install_scenario_templates.py -c postgres.tsccfg`
4. (optional Testfield Lower Saxony) `git clone https://github.com/DLR-TS/sumo-scenarios` and `./install_scenario_templates.py -p ../sumo-scenarios/`

## Running
1. Prepare the credentials file postgres.tsccfg as described in section Installing
2. Run `./tsc_main.py -c postgres.tsccfg --daemon` 

The `--daemon`-flag lets the tsc loop look for new simulation requests. Alternatively you can run a specific simulation key like this: `./tsc_main.py --sim-key 2021y_06m_04d_11h_04m_34s_855ms -c postgres.tsccfg`.

If you want to override certain simulation parameters on the command line use the option `--sim-param` for instance `--sim-param SUMO_TEMPLATE_FOLDER:siemensbahn,SUMO_DESTINATION_FOLDER:siemensbahn,SUMO_MODES:'0;1;2;3;5;6;261;517'`. For a list of available parameters have a look at the relevant database table `public.simulation_parameters` or at constants.py (the SP class).
