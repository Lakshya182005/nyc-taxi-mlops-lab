"""Training: window -> model -> evaluation -> challenger, with the gate in between.

training_set   UNLOADs the window, the holdout month and the zone-pair distances to the artifact bucket
trained_model  fits v2 (LightGBM), logs it to MLflow, registers a version with the contract's tags
eval_report    scores the new version and the champion (or the v1 baseline) on the same holdout
beats_champion blocking: inputs match the contract, MAE beats the champion by MARGIN, p95 within budget
challenger     moves the `challenger` alias. Never `champion`: that's S3's approval-gated workflow.

Decision records: 007 (what stays in the notebook), 008 (metric and margin), 009 (training window).
"""

import os
from importlib.metadata import version as pkg_version
from pathlib import Path

import dagster as dg
import mlflow
import tripmodel
from tripmodel import BaselineModel, LightGBMModel, evaluate, model_signature

from ..contracts import features_contract, mlflow_contract
from ..resources import ArtifactBucket, MlflowTracking, RedshiftData
from ..runs import last_metadata

TRAIN_MONTHS = 3  # the three months before the holdout (record 009)
HOLDOUT_MONTHS = 1  # the newest loaded month: the closest thing to next month's traffic
MAX_TRAIN_ROWS = 3_000_000  # all 9.5M rows gain 0.02 min of MAE for 2.5x the fit time (measured)
HOLDOUT_SAMPLE = 500_000  # same seeded rows for both models: MAE's standard error ~0.007 min, far under the margin
MARGIN = 0.005  # beat the champion's MAE by 0.5% (record 008)
LATENCY_BUDGET_MS = 50.0  # single-row p95 in process; the serving SLO (S5) leaves room for HTTP
PREFIX = "training/current"

MODEL = mlflow_contract()["registered_model"]


def _unload(select: str, uri: str) -> str:
    quoted = select.replace("'", "''")
    return f"unload ('{quoted}') to '{uri}' iam_role default format as parquet cleanpath"


@dg.asset(deps=["trip_features"], group_name="model", kinds={"redshift", "s3"}, pool="redshift")
def training_set(context: dg.AssetExecutionContext, redshift: RedshiftData, artifacts: ArtifactBucket) -> dg.MaterializeResult:
    months = [r["trip_month"] for r in redshift.query("select distinct trip_month from staging.trip_features order by 1")]
    if len(months) < TRAIN_MONTHS + HOLDOUT_MONTHS:
        raise dg.Failure(f"need {TRAIN_MONTHS + HOLDOUT_MONTHS} months of trip_features, have {months}")
    holdout, window = months[-1], months[-1 - TRAIN_MONTHS : -1]
    in_window = ", ".join(f"'{m}'" for m in window)
    cols = "pickup_zone_id, dropoff_zone_id, pickup_hour, pickup_dow, duration_min"
    redshift.execute(_unload(f"select {cols} from staging.trip_features where trip_month in ({in_window})", artifacts.uri(f"{PREFIX}/train/")))
    redshift.execute(_unload(f"select {cols} from staging.trip_features where trip_month = '{holdout}'", artifacts.uri(f"{PREFIX}/holdout/")))
    # The distance lookup: an aggregate of the window only, so no holdout trip informs it.
    redshift.execute(_unload(
        "select pickup_zone_id, dropoff_zone_id, median(trip_distance) as est_distance_miles from staging.stg_trips "
        f"where trip_month in ({in_window}) and duration_min > 0 and duration_min <= 180 and trip_distance > 0 "
        "and pickup_zone_id between 1 and 263 and dropoff_zone_id between 1 and 263 group by 1, 2",
        artifacts.uri(f"{PREFIX}/distances/"),
    ))
    counts = redshift.query(
        f"select sum(case when trip_month in ({in_window}) then 1 else 0 end) as train, "
        f"sum(case when trip_month = '{holdout}' then 1 else 0 end) as holdout from staging.trip_features"
    )[0]
    manifest = {"training_window": f"{window[0]}..{window[-1]}", "holdout_month": holdout,
                "train_rows": int(counts["train"]), "holdout_rows": int(counts["holdout"]), "prefix": artifacts.uri(PREFIX)}
    artifacts.write_json(f"{PREFIX}/manifest.json", manifest)
    return dg.MaterializeResult(metadata={k: v if isinstance(v, str) else dg.MetadataValue.int(v) for k, v in manifest.items()})


@dg.asset(deps=[training_set], group_name="model", kinds={"mlflow", "lightgbm"})
def trained_model(context: dg.AssetExecutionContext, artifacts: ArtifactBucket, tracking: MlflowTracking) -> dg.MaterializeResult:
    manifest = artifacts.read_json(f"{PREFIX}/manifest.json")
    train = artifacts.read_parquet(f"{PREFIX}/train/")
    if len(train) > MAX_TRAIN_ROWS:
        train = train.sample(MAX_TRAIN_ROWS, random_state=0)
    distances = artifacts.read_parquet(f"{PREFIX}/distances/")
    model = LightGBMModel().fit(train, distances)

    client = tracking.client()
    with mlflow.start_run(run_name=f"lightgbm {manifest['training_window']}") as run:
        mlflow.log_params({"model": "lightgbm", "training_window": manifest["training_window"],
                           "holdout_month": manifest["holdout_month"], "train_rows": len(train),
                           "num_rounds": 300, **{f"lgb.{k}": v for k, v in model.params.items()}})
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=model,
            signature=model_signature(),
            input_example=train[tripmodel.REQUIRED].head(3).astype("int64"),
            code_paths=[str(Path(tripmodel.__file__).parent)],
            pip_requirements=[f"{p}=={pkg_version(p)}" for p in ("lightgbm", "pandas", "numpy")] + [f"mlflow-skinny=={pkg_version('mlflow')}"],
            registered_model_name=MODEL,
        )
    version = str(info.registered_model_version)
    tags = {"training_window": manifest["training_window"], "holdout_month": manifest["holdout_month"],
            "features_version": str(features_contract()["version"]), "git_sha": os.environ.get("GIT_SHA", "unknown")}
    for k, v in tags.items():
        client.set_model_version_tag(MODEL, version, k, v)
    return dg.MaterializeResult(metadata={"version": version, "run_id": run.info.run_id, "train_rows": dg.MetadataValue.int(len(train))})


@dg.asset(deps=[trained_model], group_name="model", kinds={"mlflow"})
def eval_report(context: dg.AssetExecutionContext, artifacts: ArtifactBucket, redshift: RedshiftData, tracking: MlflowTracking) -> dg.MaterializeResult:
    version = last_metadata(context.instance, "trained_model")["version"]
    holdout = artifacts.read_parquet(f"{PREFIX}/holdout/")
    if len(holdout) > HOLDOUT_SAMPLE:  # a full month is 3.5M rows: ~2 minutes per model on t4g.large's two cores
        holdout = holdout.sample(HOLDOUT_SAMPLE, random_state=0)
    boroughs = {int(r["location_id"]): r["borough"] for r in redshift.query("select location_id, borough from ingest.taxi_zones")}
    client = tracking.client()

    new = evaluate(mlflow.pyfunc.load_model(f"models:/{MODEL}/{version}").predict, holdout, boroughs)
    try:
        champ = client.get_model_version_by_alias(MODEL, "champion")
        against = f"champion v{champ.version}"
        reference = evaluate(mlflow.pyfunc.load_model(f"models:/{MODEL}@champion").predict, holdout, boroughs)
    except mlflow.exceptions.MlflowException:
        against = "v1 baseline (no champion yet)"
        baseline = BaselineModel().fit(artifacts.read_parquet(f"{PREFIX}/train/"), artifacts.read_parquet(f"{PREFIX}/distances/"))
        reference = evaluate(lambda df: baseline.predict(None, df), holdout, boroughs)

    mv = client.get_model_version(MODEL, version)
    for k, v in new.items():
        client.log_metric(mv.run_id, k, v)
    client.log_metric(mv.run_id, "champion_mae_min", reference["mae_min"])
    for k in ("mae_min", "p95_latency_ms"):
        client.set_model_version_tag(MODEL, version, k, f"{new[k]:.4f}")
    client.set_model_version_tag(MODEL, version, "champion_mae_min", f"{reference['mae_min']:.4f}")
    inputs = mlflow.models.get_model_info(f"models:/{MODEL}/{version}").signature.inputs.input_names()
    return dg.MaterializeResult(metadata={
        "version": version, "compared_with": against, "inputs": dg.MetadataValue.json(inputs),
        "mae_min": new["mae_min"], "champion_mae_min": reference["mae_min"], "p95_latency_ms": new["p95_latency_ms"],
        **{k: v for k, v in new.items() if k.startswith("mae_min.")},
    })


@dg.asset_check(asset=eval_report, blocking=True,
                description="The new version uses only contract inputs, beats the champion's MAE by the margin, and is fast enough.")
def beats_champion(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    m = last_metadata(context.instance, "eval_report")
    contract = features_contract()
    expected = [c["name"] for c in contract["inputs"]] + [c["name"] for c in contract["derived"]]
    problems = []
    if list(m["inputs"]) != expected:
        problems.append(f"inputs {m['inputs']} aren't the contract's {expected}")
    if not m["mae_min"] <= m["champion_mae_min"] * (1 - MARGIN):
        problems.append(f"MAE {m['mae_min']:.3f} doesn't beat {m['compared_with']} ({m['champion_mae_min']:.3f}) by {MARGIN:.0%}")
    if m["p95_latency_ms"] > LATENCY_BUDGET_MS:
        problems.append(f"p95 {m['p95_latency_ms']:.1f} ms over the {LATENCY_BUDGET_MS:.0f} ms budget")
    return dg.AssetCheckResult(
        passed=not problems,
        severity=dg.AssetCheckSeverity.ERROR,
        description="; ".join(problems) or f"v{m['version']} beats {m['compared_with']}: {m['mae_min']:.3f} vs {m['champion_mae_min']:.3f} min",
        metadata={"version": str(m["version"]), "mae_min": float(m["mae_min"]), "champion_mae_min": float(m["champion_mae_min"])},
    )


@dg.asset(deps=[eval_report], group_name="model", kinds={"mlflow"})
def challenger(context: dg.AssetExecutionContext, tracking: MlflowTracking) -> dg.MaterializeResult:
    version = str(last_metadata(context.instance, "eval_report")["version"])
    tracking.client().set_registered_model_alias(MODEL, "challenger", version)
    return dg.MaterializeResult(metadata={"version": version, "alias": "challenger"})


train_model = dg.define_asset_job("train_model", selection=dg.AssetSelection.assets(training_set, trained_model, eval_report, challenger))

