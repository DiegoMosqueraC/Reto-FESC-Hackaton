"""Estado de migración por dominio (LEGACY -> DUAL -> MODERN).

Se guarda en el volumen del gateway; si no existe se usan los estados de
docs/migration-plan.md. Uso desde la terminal (lo usa rollback.sh):

    docker compose exec -T gateway python -m app.migration set affiliations LEGACY
    docker compose exec -T gateway python -m app.migration show
"""

import json
import os
import sys

STATE_PATH = os.environ.get("MIGRATION_STATE", "/app/data/migration.json")
STATES = ("LEGACY", "DUAL", "MODERN")
DEFAULTS = {"affiliations": "DUAL", "retirements": "LEGACY", "companies": "LEGACY", "contributions": "LEGACY"}


def load():
    domains = dict(DEFAULTS)
    try:
        with open(STATE_PATH, encoding="utf-8") as handle:
            domains.update(json.load(handle))
    except (OSError, ValueError):
        pass
    return domains


def set_state(domain, state):
    if domain not in DEFAULTS:
        raise ValueError("Dominio desconocido: {0}. Use: {1}".format(domain, ", ".join(DEFAULTS)))
    if state not in STATES:
        raise ValueError("Estado inválido: {0}. Use: {1}".format(state, ", ".join(STATES)))
    domains = load()
    domains[domain] = state
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    temporary = STATE_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(domains, handle)
    os.replace(temporary, STATE_PATH)  # escritura atómica
    return domains


def main(argv):
    if len(argv) == 3 and argv[0] == "set":
        try:
            print(json.dumps({"domains": set_state(argv[1], argv[2].upper())}))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0
    if argv == ["show"]:
        print(json.dumps({"domains": load()}))
        return 0
    print("Uso: python -m app.migration set <dominio> <LEGACY|DUAL|MODERN> | show", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
