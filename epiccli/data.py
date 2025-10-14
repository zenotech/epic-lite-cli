import click
import requests
import os
import json

def get_data_keys(project_config):
    """Fetches and displays temporary AWS session keys for direct data access.

    This function calls the /data/session endpoint of the EPIC API to retrieve
    temporary AWS credentials (Access Key ID, Secret Access Key, and Session Token).
    It then prints a series of `export` commands that the user can run in their
    shell to configure their environment for direct access to the project's
    S3 data bucket using tools like the AWS CLI.

    Args:
        project_config (dict): A dictionary containing the configuration for the
            active project, including 'epic_api_url', 'data_bucket_name', and 'region'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/data/session", headers=headers)
        response.raise_for_status()
        keys = response.json()
        click.echo("\n# Run the following commands in your shell to configure your data session:")
        click.echo(f"export AWS_ACCESS_KEY_ID='{keys.get('aws_access_key_id')}'")
        click.echo(f"export AWS_SECRET_ACCESS_KEY='{keys.get('aws_secret_access_key')}'")
        click.echo(f"export AWS_SESSION_TOKEN='{keys.get('aws_session_token')}'")
        click.echo(f"export EPIC_S3_BUCKET='{project_config.get('data_bucket_name')}'")
        click.echo(f"export AWS_REGION='{project_config.get('region')}'")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error fetching data session keys: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")