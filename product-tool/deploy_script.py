"""
Deploy script for Pookie Style Cloud Function (v2)
Copies source to a temp dir (no spaces in path) and deploys via gcloud.
"""
import subprocess
import sys
import os
import shutil

# --- Config ---
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = r"C:\tmp\pookie-deploy"
ENV_FILE = os.path.join(DEPLOY_DIR, ".env.yaml")
gcloud = r"C:\Users\ADMIN\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
DOCKER_REPO = "projects/pookie-style-automation/locations/asia-south1/repositories/gcf-artifacts"

# Files needed for deployment (no deprecated files)
DEPLOY_FILES = [
    "main.py",
    "requirements.txt",
    os.path.join("services", "__init__.py"),
    os.path.join("services", "openai_service.py"),
    os.path.join("services", "replicate_service.py"),
    os.path.join("services", "shopify_service.py"),
]


def prepare_deploy_dir():
    """Copy only needed files to the deploy directory (no spaces in path)."""
    # Clean previous deploy
    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)

    os.makedirs(os.path.join(DEPLOY_DIR, "services"), exist_ok=True)

    for f in DEPLOY_FILES:
        src = os.path.join(SOURCE_DIR, f)
        dst = os.path.join(DEPLOY_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Copied: {f}")
        else:
            print(f"  WARNING: {f} not found at {src}")

    # Copy .env.yaml if it exists alongside this script
    env_src = os.path.join(SOURCE_DIR, ".env.yaml")
    if os.path.exists(env_src):
        shutil.copy2(env_src, ENV_FILE)
        print("  Copied: .env.yaml")
    else:
        print(f"  WARNING: .env.yaml not found at {env_src}")
        print("  Make sure .env.yaml exists in the deploy dir before running gcloud.")


def deploy():
    """Run gcloud functions deploy."""
    if not os.path.exists(ENV_FILE):
        print(f"\nERROR: {ENV_FILE} not found. Cannot deploy without env vars.")
        print("Copy .env.yaml.example to .env.yaml and fill in your keys.")
        sys.exit(1)

    cmd = [
        gcloud, "functions", "deploy", "create-product",
        "--gen2",
        "--runtime=python312",
        "--region=asia-south1",
        "--trigger-http",
        "--allow-unauthenticated",
        "--timeout=300",
        "--memory=512MB",
        f"--source={DEPLOY_DIR}",
        "--entry-point=create_product_handler",
        f"--env-vars-file={ENV_FILE}",
        f"--docker-repository={DOCKER_REPO}",
        "--quiet",
    ]

    print(f"\nDeploying from: {DEPLOY_DIR}")
    print(f"Entry point: create_product_handler")
    print("Running gcloud deploy...\n")

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # Save logs
    log_file = os.path.join(SOURCE_DIR, "deploy_log.txt")
    err_file = os.path.join(SOURCE_DIR, "deploy_err.txt")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(r.stdout)
    with open(err_file, "w", encoding="utf-8") as f:
        f.write(r.stderr)

    if r.returncode == 0:
        print("✅ Deploy SUCCESSFUL!")
        print(f"Logs: {log_file}")
    else:
        print(f"❌ Deploy FAILED (exit code {r.returncode})")
        print(f"Error log: {err_file}")
        print(f"\nLast 20 lines of stderr:\n{chr(10).join(r.stderr.splitlines()[-20:])}")

    return r.returncode


if __name__ == "__main__":
    print("=" * 50)
    print("Pookie Style — Cloud Function Deploy (v2)")
    print("=" * 50)
    print(f"\nSource: {SOURCE_DIR}")
    print(f"Deploy dir: {DEPLOY_DIR}\n")

    print("Step 1: Preparing deploy directory...")
    prepare_deploy_dir()

    print("\nStep 2: Deploying to GCP...")
    exit_code = deploy()
    sys.exit(exit_code)
