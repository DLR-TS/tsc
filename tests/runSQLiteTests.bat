call testEnv.bat %1
set SIP_HOME=%CD%\..
set TSC_HOME=%CD%\..
set TEXTTEST_HOME=%SIP_HOME%\tests
set TSC_DATA=%SIP_HOME%
set TSC_SERVER=sqlite3.tsccfg
%TEXTTESTPY% -a tsc.sqlite3
