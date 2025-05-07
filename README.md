# TAPAS-SUMO-Coupling (tsc)
Combining traffic demand estimation with microscopic traffic simulation

## Requirements

### SUMO
You need to have a working SUMO installation and your environment variable SUMO_HOME needs to be set.
On ubuntu you could try:

```
sudo add-apt-repository ppa:sumo/stable
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc
```

Then open a new login shell and check whether `echo $SUMO_HOME` generates an output like `/usr/share/sumo`. This directory should contain
subdirectories like `data` and `tools`.

### Python
The scripts should work with Python 3.7 or later (if absolutely necessary, you might try Python 2.7).
If you prefer installing via your package manager do something like
`sudo apt-get install python3-psycopg2 python3-rtree python3-pandas`.
The psycopg2 adapter is needed for database communication.
It is strongly recommended to have the rtree module which speeds up several lookup procedures and pandas
if you need GTFS import.

### Virtual Environments
If you don't want to mess with your system or don't have sudo rights, you can do everything in a virtual environment:

```
python3 -m venv tsc_env
. tsc_env/bin/activate
git clone https://github.com/DLR-TS/tsc
python3 -m pip install -r tsc/requirements.txt
python3 -m pip install eclipse-sumo
```

You can also mix the two approaches for instance if you want to try different versions of SUMO or tsc
but alway use the dependencies from the underlying system.


## Installing
If you did not do it before start to clone this repo `git clone https://github.com/DLR-TS/tsc`.

For bleeding edge:

1. Change the directory `cd tsc`.
2. Upgrade pip `python3 -m pip install -U pip`.
3. Run `python3 -m pip install --user .` (developers may want to use `python3 -m pip install -e --user .` here for an editable install).

Make sure you have the relevant bin directories in your PATH (you should be able to run `sumo` and `tsc_main`). Now install the scenarios:

4. Copy postgres_template.tsccfg (e.g. to postgres.tsccfg) and enter the database connection details (server, user, passwd)
5. Install scenarios for Berlin and Testfield Lower Saxony `git clone --recursive --depth 1 https://github.com/DLR-TS/sumo-scenarios` and `tsc_install -c postgres.tsccfg -p ../sumo-scenarios/`.
   This will try to install other scenarios as well but you can safely ignore the corresponding warnings. If you only want selected scenarios, you can use the -s option like `-s konstanz`.

### Optional old scenarios
1. Make sure you have git-lfs on your system (`sudo apt-get install git-lfs`) and activated for your user (`git lfs install`).
2. Do another `git pull` in the tsc directory if you cloned without having lfs active.
3. Run `tsc_install -c postgres.tsccfg` directly in the tsc checkout.

The installations need the database connection only if you plan to use scenarios with (Germany wide) background traffic.
If you don't need it, you can omit the `-c postgres.tsccfg` part.

## Running
1. Prepare the credentials file postgres.tsccfg as described in section Installing
2. Run `tsc_main -c postgres.tsccfg --daemon`

The `--daemon`-flag lets the tsc loop look for new simulation requests. Alternatively you can run a specific
simulation key like this: `tsc_main --sim-key 2021y_06m_04d_11h_04m_34s_855ms -c postgres.tsccfg`.

If you want to override certain simulation parameters on the command line use the option `--sim-param` for instance
`--sim-param SUMO_TEMPLATE_FOLDER:siemensbahn,SUMO_DESTINATION_FOLDER:siemensbahn,SUMO_MODES:'0;1;2;3;5;6;261;517'`.
For a list of available parameters have a look at the relevant database table `public.simulation_parameters` or at constants.py (the SP class).

## Testing
This requires [texttest](https://www.texttest.org/) to be installed (using `python3 -m pip install --user texttest` or the windows installer).
To run the tests you will either need a running postgresql database or you will need to configure your sqlite installation such that it can use the spatialite extension.
Most of the time it suffices to install mod_spatialite (`sudo apt-get install libsqlite3-mod-spatialite`). It is very likely that this works only with python3.
If you have everything installed run one of the scripts in the test directory which should fire up the texttest GUI
and allow you to run selected or all tests. Please be aware that you cannot run the tests in parallel
if you use PostGreSQL because they all access the same database.

## Setting up a new scenario
The `tsc_install` script sets up a scenario template for every subdirectory in its data dir.
So the first step to add a new scenario is to add a new subdirectory which needs at least
1. A SUMO network named `net.net.xml.gz`.
2. A definition of vehicle types named `vtypes.xml`
While the tsc tooling allows a fine grained configuration those two files are everything you need to get started,
more details are given below.

### The network
The `tsc_install` script supports the creation of a network from OpenStreetMap data.
If you provide one or multiple `template_gen*.netccfg` file(s) the script will execute them in lexical order
and the last call should generate the needed `net.net.xml.gz`. This way it is possible to rebuild the network
on every new installation. If you do so you need to provide the input (OSM XML) files in your data directory and
let the netccfg refer to them.

### The vehicle types
TAPAS assigns a vehicle type to every vehicle which needs to be mapped (by it's name) to a 
[SUMO vehicle type](https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html#vehicle_types).
The file `vtypes.xml` should simply list them with their properties including emission classes (if known).

### Additional data
It may be useful to have additional files in a scenario (to be described)
- Traffic assignment zones for suburban areas
- landmarks to speed up routing

Furthermore you can define custom scripts (with the name `setup.py`) which get called in the installation process
and can modify or generate the rquired inputs.

## Documentation
For a (german) description of the database layout and some details on the process have a look at the "Lastenheft" in the docs folder.
