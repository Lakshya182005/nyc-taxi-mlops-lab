# Reference wiring for S2: the exploration notebook, and MLflow on the platform host opened to it.

module "notebook" {
  source    = "../modules/notebook"
  subnet_id = data.aws_subnet.primary.id
  repo_url  = "https://github.com/${var.github_repo}.git"
  env = {
    MLFLOW_TRACKING_URI = "http://${module.platform.private_ip}:5000"
    REDSHIFT_CLUSTER_ID = module.redshift.cluster_id
    REDSHIFT_DATABASE   = module.redshift.database
    REDSHIFT_DB_USER    = "labadmin"
    LAB_ARTIFACT_BUCKET = module.artifact_bucket.name
  }
}

resource "aws_vpc_security_group_ingress_rule" "mlflow_from_notebook" {
  security_group_id            = aws_security_group.platform.id
  referenced_security_group_id = module.notebook.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5000
  to_port                      = 5000
  description                  = "MLflow from the notebook"
}

output "notebook_name" {
  value = module.notebook.name
}
