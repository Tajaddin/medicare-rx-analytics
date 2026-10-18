#!/usr/bin/env bash
# Validate every Power BI project file against the JSON schema it names in "$schema" (Microsoft's published
# schemas, fetched over HTTPS by check-jsonschema). TMDL has no JSON schema; Power BI Desktop is its check.
#
#   scripts/validate_pbir.sh [bi/powerbi]
set -euo pipefail

dir=${1:-bi/powerbi}
mapfile -t files < <(find "$dir" -type f \( -name '*.json' -o -name '*.pbir' -o -name '*.pbism' -o -name '*.pbip' \) \
  -not -path '*/StaticResources/*' -not -path '*/.pbi/*' | sort)
((${#files[@]})) || { echo "no Power BI files under $dir" >&2; exit 1; }

failed=0
for f in "${files[@]}"; do
  # shellcheck disable=SC2016  # $schema is a JSON key, not a shell variable
  schema=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("$schema", ""))' "$f")
  if [[ -z $schema ]]; then
    echo "no \$schema: $f" >&2
    failed=1
    continue
  fi
  check-jsonschema --schemafile "$schema" "$f" >/dev/null || { echo "invalid: $f" >&2; failed=1; }
done
echo "${#files[@]} files checked against their schemas"
exit "$failed"
