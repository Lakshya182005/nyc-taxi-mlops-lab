"""feature_contract: staging.trip_features against contracts/features.yaml. Blocking, as mlflow.yaml
requires: a column the contract doesn't list (gameday E1's fare_amount) or a value out of range stops
the run before anything trains on it."""

import dagster as dg

from ..contracts import features_contract
from ..partitions import trip_months
from ..resources import RedshiftData
from .features import trip_features

# svv_columns.data_type for the contract's types
REDSHIFT_TYPE = {"integer": "integer", "smallint": "smallint", "double precision": "double precision"}


def expected_columns(contract: dict) -> list[tuple[str, str]]:
    cols = contract["keys"] + contract["inputs"] + [contract["label"]]
    return [(c["name"], "character" if c["type"].startswith("char") else REDSHIFT_TYPE[c["type"]]) for c in cols]


def column_problems(expected: list[tuple[str, str]], actual: list[tuple[str, str]], forbidden: list[str]) -> list[str]:
    problems = [f"forbidden post-trip column {n}" for n, _ in actual if n in forbidden]
    problems += [f"unexpected column {n} ({t})" for n, t in actual if (n, t) not in expected and n not in forbidden]
    problems += [f"missing column {n} ({t})" for n, t in expected if (n, t) not in actual]
    return problems


@dg.asset_check(
    asset=trip_features,
    partitions_def=trip_months,
    blocking=True,
    description="Columns are exactly contracts/features.yaml (no post-trip fields) and this month's values are in range.",
)
def feature_contract(context: dg.AssetCheckExecutionContext, redshift: RedshiftData) -> dg.AssetCheckResult:
    contract = features_contract()
    schema, table = contract["table"].split(".")
    actual = [(r["column_name"], r["data_type"]) for r in redshift.query(
        f"select column_name, data_type from svv_columns where table_schema = '{schema}' "
        f"and table_name = '{table}' order by ordinal_position")]
    problems = column_problems(expected_columns(contract), actual, contract["forbidden"])
    if not problems:
        ranged = [c for c in contract["inputs"] + [contract["label"]] if "range" in c]
        bounds = ", ".join(f"min({c['name']}) as min_{c['name']}, max({c['name']}) as max_{c['name']}" for c in ranged)
        r = redshift.query(f"select count(*) as rows, {bounds} from {contract['table']} where trip_month = '{context.partition_key}'")[0]
        for c in ranged:
            lo, hi = c["range"]
            if r[f"min_{c['name']}"] is not None and not (lo <= float(r[f"min_{c['name']}"]) and float(r[f"max_{c['name']}"]) <= hi):
                problems.append(f"{c['name']} outside {lo}..{hi}")
    return dg.AssetCheckResult(
        passed=not problems,
        severity=dg.AssetCheckSeverity.ERROR,
        description="; ".join(problems[:5]) or "matches contracts/features.yaml",
        metadata={"problems": dg.MetadataValue.json(problems)},
    )
