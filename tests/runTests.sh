#!/bin/bash
#Bash script for the test run.
#sets environment variables respecting SUMO_BINDIR and starts texttest

if test x"$SUMO_HOME" = x; then
  export SUMO_HOME="$HOME/sumo"
fi
export ACTIVITYGEN_BINARY="$SUMO_HOME/bin/activitygen$SUFFIX"
export DFROUTER_BINARY="$SUMO_HOME/bin/dfrouter$SUFFIX"
export DUAROUTER_BINARY="$SUMO_HOME/bin/duarouter$SUFFIX"
export JTRROUTER_BINARY="$SUMO_HOME/bin/jtrrouter$SUFFIX"
export MAROUTER_BINARY="$SUMO_HOME/bin/marouter$SUFFIX"
export NETCONVERT_BINARY="$SUMO_HOME/bin/netconvert$SUFFIX"
export NETEDIT_BINARY="$SUMO_HOME/bin/netedit$SUFFIX"
export NETGENERATE_BINARY="$SUMO_HOME/bin/netgenerate$SUFFIX"
export OD2TRIPS_BINARY="$SUMO_HOME/bin/od2trips$SUFFIX"
export POLYCONVERT_BINARY="$SUMO_HOME/bin/polyconvert$SUFFIX"
export SUMO_BINARY="$SUMO_HOME/bin/sumo$SUFFIX"
export GUISIM_BINARY="$SUMO_HOME/bin/sumo-gui$SUFFIX"
export PYTHON="python"
export SIP_HOME="$HOME/SiP"
export TSC_HOME="$PWD/.."
export TEXTTEST_HOME="$SIP_HOME/tests"
export TSC_DATA="$SIP_HOME/projects/tapas"

if which texttest &> /dev/null; then
  texttest "$@"
else
  texttest.py "$@"
fi
