"""Reference tests for S2: the feature contract (E1), and the training job end to end with a local
MLflow, a fake Redshift that UNLOADs synthetic trips, and the artifact bucket as a directory."""

import dagster as dg
import mlflow
import pytest
from fakes import LocalArtifacts, unloading_redshift
from mlflow import MlflowClient

from labpipes.contracts import features_contract
from labpipes.defs.feature_check import column_problems, expected_columns
from labpipes.defs.training import beats_champion, challenger, eval_report, trained_model, training_set
from labpipes.resources import MlflowTracking


def test_contract_columns_pass_and_a_leaky_one_fails():
    contract = features_contract()
    expected = expected_columns(contract)
    assert column_problems(expected, expected, contract["forbidden"]) == []
    leaky = expected + [("fare_amount", "double precision")]  # gameday E1
    assert column_problems(expected, leaky, contract["forbidden"]) == ["forbidden post-trip column fare_amount"]
    assert column_problems(expected, expected[:-1], contract["forbidden"]) == ["missing column duration_min (double precision)"]


@pytest.fixture
def env(tmp_path):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    mlflow.set_tracking_uri(uri)
    mlflow.create_experiment("trip-duration", artifact_location=str(tmp_path / "mlartifacts"))
    root = tmp_path / "s3"
    root.mkdir()
    return {
        "instance": dg.DagsterInstance.ephemeral(),
        "resources": {
            "redshift": unloading_redshift(str(root)),
            "artifacts": LocalArtifacts(bucket="artifacts", root=str(root)),
            "tracking": MlflowTracking(tracking_uri=uri),
        },
        "client": MlflowClient(uri),
    }


def train(env):
    return dg.materialize([training_set, trained_model, eval_report, challenger, beats_champion],
                          instance=env["instance"], resources=env["resources"], raise_on_error=False)


def test_first_model_beats_the_baseline_and_becomes_challenger(env):
    result = train(env)
    assert result.success, [e.message for e in result.all_events if e.is_failure]
    client = env["client"]
    v = client.get_model_version_by_alias("trip-duration", "challenger")
    tags = v.tags
    assert tags["training_window"] == "2024-01..2024-03" and tags["holdout_month"] == "2024-04"
    assert float(tags["mae_min"]) < float(tags["champion_mae_min"])
    with pytest.raises(mlflow.exceptions.MlflowException):
        client.get_model_version_by_alias("trip-duration", "champion")  # the pipeline never sets it


def test_an_equal_model_does_not_pass_the_margin(env):
    assert train(env).success
    client = env["client"]
    client.set_registered_model_alias("trip-duration", "champion", "1")  # what S3's workflow would do
    second = train(env)  # same data, same seed: no better than the champion
    assert not second.success
    assert str(client.get_model_version_by_alias("trip-duration", "challenger").version) == "1"
    evals = [e.event_specific_data for e in second.all_events if e.event_type_value == "ASSET_CHECK_EVALUATION"]
    assert evals and not evals[0].passed and "doesn't beat champion v1" in evals[0].description
