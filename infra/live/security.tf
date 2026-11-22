# S0: security groups and rules.
#
# Decision point: who may reach the app (ingress scope)? Record it in decisions/.
# Traffic between hosts (ports in contracts/runtime.yaml):
#   app -> platform  MLflow (5000)
#   app, platform -> llm  chat (8080) and embeddings (8081)
#   app, platform -> rds  Postgres (5432)
# There is no SSH in this lab: use SSM Session Manager for a shell and port forwarding for UIs.

resource "aws_security_group" "app" {
  name_prefix = "lab-app-"
  description = "App host: Traefik on port 80 from ingress_cidrs; egress for dependencies"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-app", role = "app" }
}

resource "aws_vpc_security_group_ingress_rule" "app_http" {
  for_each          = toset(var.ingress_cidrs)
  security_group_id = aws_security_group.app.id
  description       = "Traefik HTTP from authorized CIDR"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  description       = "Egress for Docker pulls, packages, and AWS APIs"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "platform" {
  name_prefix = "lab-platform-"
  description = "Platform host: Dagster & MLflow; egress to S3 and Redshift"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-platform", role = "platform" }
}

resource "aws_vpc_security_group_ingress_rule" "platform_mlflow_from_app" {
  security_group_id            = aws_security_group.platform.id
  description                  = "MLflow from app host"
  ip_protocol                  = "tcp"
  from_port                    = 5000
  to_port                      = 5000
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_egress_rule" "platform_all" {
  security_group_id = aws_security_group.platform.id
  description       = "Egress for packages, S3, and AWS APIs"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "llm" {
  name_prefix = "lab-llm-"
  description = "LLM host: vLLM chat and embeddings"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-llm", role = "llm" }
}

resource "aws_vpc_security_group_ingress_rule" "llm_chat_from_app" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM chat from app host"
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_embed_from_app" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM embed from app host"
  ip_protocol                  = "tcp"
  from_port                    = 8081
  to_port                      = 8081
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_chat_from_platform" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM chat from platform host"
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "llm_embed_from_platform" {
  security_group_id            = aws_security_group.llm.id
  description                  = "LLM embed from platform host"
  ip_protocol                  = "tcp"
  from_port                    = 8081
  to_port                      = 8081
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_egress_rule" "llm_all" {
  security_group_id = aws_security_group.llm.id
  description       = "Egress for model downloads and packages"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "rds" {
  name_prefix = "lab-rds-"
  description = "PostgreSQL database: port 5432 from platform and app"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "lab-rds" }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_platform" {
  security_group_id            = aws_security_group.rds.id
  description                  = "Postgres from platform host (Dagster/MLflow)"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_app" {
  security_group_id            = aws_security_group.rds.id
  description                  = "Postgres from app host (pgvector / assistant)"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.app.id
}
