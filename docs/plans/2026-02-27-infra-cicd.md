# Infra & CI/CD Plan

## Stack
- **Compute**: EC2 (t3.micro, free-tier eligible) running Docker
- **Database**: RDS PostgreSQL (db.t3.micro)
- **Container registry**: ECR
- **Secrets**: AWS Secrets Manager
- **IaC**: Terraform
- **CI/CD**: GitHub Actions

## Directory Layout

```
infra/
  local/          # existing
  aws/
    terraform/
      main.tf
      variables.tf
      outputs.tf
      vpc.tf
      ecr.tf
      rds.tf
      ec2.tf
      secrets.tf
      iam.tf
      backend.tf   # remote state config
.github/
  workflows/
    ci.yml         # lint + test on PR
    cd.yml         # build + push + deploy on merge to main
```

---

## Phase 1: Terraform Remote State

Before writing any real infra, set up remote state so Terraform state is not stored locally.

**Manually create (one-time, in AWS console or via CLI):**
- S3 bucket: `dungeon-service-tfstate`
- DynamoDB table: `dungeon-service-tfstate-lock` (partition key: `LockID`, type String)

**`backend.tf`:**
```hcl
terraform {
  backend "s3" {
    bucket         = "dungeon-service-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "dungeon-service-tfstate-lock"
    encrypt        = true
  }
}
```

---

## Phase 2: Networking (VPC)

**`vpc.tf`** — creates:
- VPC with a CIDR block
- 2 public subnets (EC2 lives here)
- 2 private subnets (RDS lives here)
- Internet gateway + route tables
- Security groups:
  - `sg_app`: allows inbound 8000 from anywhere, outbound all
  - `sg_db`: allows inbound 5432 only from `sg_app`

A private subnet for RDS is best practice even for a small project — shows you know not to expose the DB to the internet.

---

## Phase 3: ECR

**`ecr.tf`** — creates:
- ECR repository: `dungeon-service`
- Lifecycle policy: keep last 5 images (prevents runaway storage costs)

---

## Phase 4: RDS

**`rds.tf`** — creates:
- RDS PostgreSQL instance (db.t3.micro, `postgres16`)
- Subnet group using the private subnets
- Attached to `sg_db`
- Credentials sourced from variables (stored in tfvars, not committed)
- `skip_final_snapshot = true` for dev (flip this for production)

Note: Flyway still handles migrations. On deploy, GitHub Actions runs Flyway as a one-off Docker container pointed at the RDS endpoint before starting the app.

---

## Phase 5: Secrets Manager

**`secrets.tf`** — creates two secrets:
- `dungeon-service/anthropic-api-key` — stores `ANTHROPIC_API_KEY`
- `dungeon-service/db-credentials` — stores `DATABASE_URL`

The EC2 instance will pull these at container startup via the AWS CLI (see EC2 user data below). This avoids storing secrets in environment variables or docker-compose files on disk.

---

## Phase 6: IAM

**`iam.tf`** — creates:
- IAM role for EC2 instance profile with policies for:
  - `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` — to pull images
  - `secretsmanager:GetSecretValue` on the two secrets above — to read credentials at startup
- Instance profile that attaches the role to EC2

This is the key learning piece of EC2 vs App Runner — you have to wire up IAM yourself.

---

## Phase 7: EC2

**`ec2.tf`** — creates:
- EC2 instance (t3.micro, Amazon Linux 2023)
- Attached to `sg_app` in a public subnet
- IAM instance profile attached
- Key pair for SSH (generate locally, reference public key in Terraform)
- User data script that runs on first boot:
  ```bash
  #!/bin/bash
  # Install Docker
  yum install -y docker
  systemctl enable docker
  systemctl start docker

  # Install AWS CLI (included in AL2023)
  # Log in to ECR
  aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account_id>.dkr.ecr.us-east-1.amazonaws.com

  # Write a deploy script for CI to call later
  cat > /home/ec2-user/deploy.sh << 'EOF'
  #!/bin/bash
  aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account_id>.dkr.ecr.us-east-1.amazonaws.com
  docker pull <account_id>.dkr.ecr.us-east-1.amazonaws.com/dungeon-service:latest
  docker stop dungeon-service || true
  docker rm dungeon-service || true
  ANTHROPIC_API_KEY=$(aws secretsmanager get-secret-value \
    --secret-id dungeon-service/anthropic-api-key \
    --query SecretString --output text)
  DATABASE_URL=$(aws secretsmanager get-secret-value \
    --secret-id dungeon-service/db-credentials \
    --query SecretString --output text)
  docker run -d --name dungeon-service \
    -p 8000:8000 \
    -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    -e DATABASE_URL="$DATABASE_URL" \
    <account_id>.dkr.ecr.us-east-1.amazonaws.com/dungeon-service:latest
  EOF
  chmod +x /home/ec2-user/deploy.sh
  ```

**`outputs.tf`** — outputs the EC2 public IP so you don't have to look it up.

---

## Phase 8: Dockerfile Improvements

The existing Dockerfile has two issues worth fixing before using it in production:
- Runs `uv sync` twice unnecessarily
- Doesn't separate dependency install from source copy (defeats layer caching)

Update to copy `pyproject.toml` + `uv.lock` first, sync, then copy `src/`. This way Docker cache is only invalidated when deps change, not on every source change.

---

## Phase 9: GitHub Actions — CI

**`.github/workflows/ci.yml`** — triggers on pull request to `main`:

```
1. Checkout
2. Set up Python 3.12 + uv
3. uv sync
4. ruff check .
5. ruff format --check .
6. mypy src
7. pytest
```

No AWS credentials needed here — purely local.

---

## Phase 10: GitHub Actions — CD

**`.github/workflows/cd.yml`** — triggers on push to `main`:

```
1. Checkout
2. Configure AWS credentials (via GitHub OIDC — no long-lived keys)
3. Log in to ECR
4. Build Docker image, tag as :latest and :<git-sha>
5. Push both tags to ECR
6. Run Flyway migrations against RDS:
     docker run --rm flyway/flyway:11-alpine migrate \
       -url=jdbc:postgresql://<rds-endpoint>:5432/dungeon_pg_db \
       -user=... -password=... -locations=filesystem:/flyway/sql
7. SSH to EC2, run /home/ec2-user/deploy.sh
```

**GitHub OIDC** (step 2): Instead of storing `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` as GitHub secrets, configure an IAM OIDC identity provider that trusts GitHub Actions. This is the professional approach — no long-lived credentials anywhere.

GitHub secrets needed:
- `EC2_HOST` — public IP from Terraform output
- `EC2_SSH_KEY` — private key for SSH
- `DB_URL` — RDS connection string (for Flyway step only)

---

## Build Order

1. Remote state (S3 + DynamoDB) — manual one-time setup
2. VPC + security groups
3. ECR
4. RDS
5. Secrets Manager (populate secrets manually after creation)
6. IAM roles + instance profile
7. EC2
8. Verify: SSH in, manually run deploy.sh with a test image
9. Fix Dockerfile layer caching
10. GitHub Actions CI workflow
11. GitHub Actions CD workflow (OIDC setup first, then the workflow)
12. End-to-end test: open a PR → CI runs; merge → CD deploys
