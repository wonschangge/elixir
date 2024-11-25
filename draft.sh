./script.sh parse-defs 59bddcf0b30c419c6611494abaf52d1b4138b776   br_connection.c   C > 1_default
./script.sh parse-defs 59bddcf0b30c419c6611494abaf52d1b4138b776   br_connection.c C > 2_default

curl http://127.0.0.1/api/ident/communication_dsoftbus/arg?version=latest&family=C

ctags --list-kinds-full | awk '{print $1 "," $2, "," $3 "," $4 "," $5 "," $6 "," substr($0, index($0, $7))}'


./script.sh parse-defs 8e0d72b7359849a7e1eca404753cf96435529bc0  buildEnd.config.ts  TS
./script.sh parse-defs 4167b96a90a280279153e79ec51fac5e9a52cad9  vitest.config.ts  TS
./script.sh parse-defs a295d4fc41adb66a139f6ec3c28f68ee57886d25  fsUtils.ts  TS

ctags --list-kinds-full=TypeScript

curl http://127.0.0.1/api/ident/vite/CLIShortcut?version=latest&family=TS

