call testEnv.bat %1
set SIP_HOME=%CD%\..
set TSC_HOME=%CD%\..
set TEXTTEST_HOME=%SIP_HOME%\tests
set TSC_DATA=%SIP_HOME%
%TEXTTESTPY% -a tapas_osmVEU.tsc