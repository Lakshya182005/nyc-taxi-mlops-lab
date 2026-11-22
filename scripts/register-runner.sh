#!/usr/bin/env bash
# Register an EC2 host as a self-hosted GitHub Actions runner over SSM.
#
#   scripts/register-runner.sh [app|platform|llm]
#
# Constraints: no SSH (uses SSM Run Command), tokens never logged or printed.
set -euo pipefail
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""

role="${1:-app}"
case "$role" in
  app|platform|llm) ;;
  *) echo "usage: $0 [app|platform|llm]" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"

# Verify AWS credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials missing or expired: export them from Learner Lab > AWS Details" >&2
  exit 1
fi

# Verify gh authentication and get repo
if ! repo=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null); then
  echo "gh is not authenticated or not in a git repo. Run: gh auth login" >&2
  exit 1
fi

# Check instance id from terraform output
iid=$(terraform -chdir="$root/infra/live" output -raw "${role}_instance_id" 2>/dev/null || true)
if [[ -z "$iid" || "$iid" == "No outputs found"* ]]; then
  echo "Instance ID for ${role} not found in terraform outputs. Has infra/live been applied?" >&2
  exit 1
fi

state=$(aws ec2 describe-instances --instance-ids "$iid" --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "not-found")
if [[ "$state" != "running" ]]; then
  echo "Host $iid ($role) is in state '$state' (must be 'running')" >&2
  exit 1
fi

# Check if already registered and online
existing_status=$(gh api "repos/$repo/actions/runners" -q ".runners[] | select(.name==\"lab-$role\") | .status" 2>/dev/null || true)
if [[ "$existing_status" == "online" ]]; then
  echo "Runner lab-$role is already registered and online on $repo."
  exit 0
fi

echo "Registering runner lab-$role on $repo via SSM on $iid..."

# Get registration token (never printed or logged)
token=$(gh api -X POST "repos/$repo/actions/runners/registration-token" -q .token)
if [[ -z "$token" ]]; then
  echo "Failed to get runner registration token from GitHub" >&2
  exit 1
fi

# Get latest runner download URL for arm64
runner_url=$(gh api "repos/$repo/actions/runners/downloads" -q '.[] | select(.os=="linux" and .architecture=="arm64") | .download_url' | head -n1)
runner_tar=$(basename "$runner_url")

ssm_script=$(cat <<SSM_EOF
set -eux
cd /opt/actions-runner
if [[ ! -f ./config.sh ]]; then
  curl -fsSL -o "$runner_tar" "$runner_url"
  tar xzf "./$runner_tar"
  chown -R runner:runner /opt/actions-runner
fi

if [[ -f ./svc.sh ]]; then
  ./svc.sh stop || true
  ./svc.sh uninstall || true
fi

sudo -u runner ./config.sh --url "https://github.com/$repo" --token "$token" --name "lab-$role" --labels "lab-$role" --unattended --replace
./svc.sh install runner
./svc.sh start
SSM_EOF
)

params=$(jq -cn --arg script "$ssm_script" '{commands: [$script]}')
cmd_id=$(aws ssm send-command \
  --instance-ids "$iid" \
  --document-name AWS-RunShellScript \
  --comment "Register runner lab-$role" \
  --parameters "$params" \
  --query Command.CommandId \
  --output text)

echo "SSM command sent ($cmd_id). Waiting for runner setup..."
status="Pending"
tries=0
while [[ "$status" =~ ^(Pending|InProgress|Delayed)$ ]]; do
  ((++tries <= 60)) || { echo "Timed out waiting for runner registration SSM command" >&2; exit 1; }
  sleep 3
  status=$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query Status --output text 2>/dev/null || echo "Pending")
done

if [[ "$status" != "Success" ]]; then
  echo "SSM registration failed with status: $status" >&2
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query StandardErrorContent --output text >&2 || true
  exit 1
fi

echo "Runner lab-$role successfully registered and started on $iid."
