#!/usr/bin/env bash

while IFS=": " read key value
do
    case "${key}" in
        location)
            VERSION=${value//[$'\t\r\n']}
            VERSION=${VERSION##*/}
            ;;
    esac
done < <(curl -fsSI https://github.com/monkeyman192/MBINCompiler/releases/latest)

curl -fsSL "https://github.com/monkeyman192/MBINCompiler/releases/download/${VERSION}/mapping.json" > mapping.json
