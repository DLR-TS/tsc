call testEnv.bat %1
set SIP_HOME=C:\Users\behr_mi\Projekte\simo
set TSC_HOME=%CD%\..
set TEXTTEST_HOME=%SIP_HOME%\tests
set TSC_DATA=%SIP_HOME%\projects\tapas
set TSC_SERVER=sqlite3.tsccfg
%TEXTTESTPY% -a tapasVEU.sqlite3
