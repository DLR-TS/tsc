call testEnv.bat %1
set TSC_SERVER=sqlite3.tsccfg
%TEXTTESTPY% -a tsc.sqlite3
