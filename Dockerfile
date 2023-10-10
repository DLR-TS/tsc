# This Dockerfile installs tsc with the publicly available berlin scenario
# to build this image run the following command
# $ docker build -t tsc - < Dockerfile.ubuntu.git
# to use it run (GUI applications need more work)
# $ docker run -it tsc bash

FROM ghcr.io/eclipse-sumo/sumo:nightly

# tsc needs lfs for the old scenarios in data, but currently we only install from sumo-scenarios
#RUN apt-get -y install git-lfs; git lfs install

RUN cd /opt; git clone --recursive --depth 1 --shallow-submodules https://github.com/DLR-TS/tsc; git clone --recursive --depth 1 --shallow-submodules https://github.com/DLR-TS/sumo-scenarios

# python packages needed (also listed in requirements.txt but we prefer the ubuntu packages)
RUN apt-get -y install python3-psycopg2

# ensure up-to-date pip
RUN python3 -m pip install -U pip

RUN cd /opt/tsc; python3 -m pip install .
#RUN cd /opt/tsc; tsc_install
RUN cd /opt/tsc; tsc_install -p /opt/sumo-scenarios/
