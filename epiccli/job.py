import click
import requests
import os
import json

def create_job(job_json_file, project_config):
    """Creates a new job by submitting a JSON file to the EPIC API.

    This function reads a job definition from a local JSON file, then sends it
    to the /job/ endpoint of the EPIC API to create a new job. The API response,
    containing the details of the created job, is printed to the console.

    Args:
        job_json_file (str): The file path to the JSON file containing the job
            definition.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_url = project_config['epic_api_url']

    try:
        with open(job_json_file) as f:
            job_data = json.load(f)

        response = requests.post(f"{api_url}/job/", headers=headers, json=job_data)
        response.raise_for_status()
        job_response = response.json()

        click.echo("Job created successfully:")
        click.echo(json.dumps(job_response, indent=4))

    except FileNotFoundError:
        click.echo(f"Error: File not found at {job_json_file}")
    except json.JSONDecodeError:
        click.echo(f"Error: Invalid JSON in {job_json_file}")
    except requests.exceptions.RequestException as e:
        try:
            error_details = e.response.json()
            click.echo(f"Error: {error_details.get('error', 'Unknown API error')}")
            if 'detail' in error_details:
                click.echo(f"Detail: {error_details['detail']}")
        except (json.JSONDecodeError, AttributeError):
            click.echo(f"Error creating job: {e}")

def list_jobs(project_config):
    """Lists all jobs for the current user.

    This function fetches a list of all jobs associated with the current user
    from the /job/ endpoint. It then prints a summary of each job, including
    its ID, name, and status.

    Args:
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/job/", headers=headers)
        response.raise_for_status()
        response_data = response.json()
        jobs = response_data.get('results', [])

        if not jobs:
            click.echo("No jobs found.")
            return

        click.echo("Current Jobs:")
        for job in jobs:
            if isinstance(job, dict):
                job_id = job.get('uuid', 'N/A')
                name = job.get('name', 'N/A')
                status = job.get('status', 'N/A')
                click.echo(f"  ID: {job_id} | Name: {name} | Status: {status}")
            else:
                click.echo(f"  Warning: Received malformed job entry: {job}")

    except requests.exceptions.RequestException as e:
        try:
            error_details = e.response.json()
            click.echo(f"Error: {error_details.get('error', 'Unknown API error')}")
            if 'detail' in error_details:
                click.echo(f"Detail: {error_details['detail']}")
        except (json.JSONDecodeError, AttributeError):
            click.echo(f"Error listing jobs: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")

def get_job(job_id, project_config):
    """Gets detailed information about a specific job.

    This function retrieves the full details of a single job by its ID from the
    /job/{job_id}/ endpoint. The detailed information is then printed to the
    console as a formatted JSON object.

    Args:
        job_id (int): The unique identifier for the job.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/job/{job_id}/", headers=headers)
        response.raise_for_status()
        job = response.json()

        click.echo("Job Details:")
        click.echo(json.dumps(job, indent=4))

    except requests.exceptions.RequestException as e:
        try:
            error_details = e.response.json()
            click.echo(f"Error: {error_details.get('error', 'Unknown API error')}")
            if 'detail' in error_details:
                click.echo(f"Detail: {error_details['detail']}")
        except (json.JSONDecodeError, AttributeError):
            click.echo(f"Error getting job details: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")

def cancel_job(job_id, project_config):
    """Cancels a specific job.

    This function sends a request to the /job/{job_id}/cancel/ endpoint to
    terminate a running job. It prints a success message if the job is
    cancelled successfully.

    Args:
        job_id (int): The unique identifier for the job to be cancelled.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.post(f"{api_url}/job/{job_id}/cancel/", headers=headers)
        response.raise_for_status()

        if response.status_code == 204:
            click.echo(f"Job {job_id} cancelled successfully.")
        else:
            click.echo(f"Received status code {response.status_code} when canceling job.")
            click.echo(response.text)

    except requests.exceptions.RequestException as e:
        try:
            error_details = e.response.json()
            click.echo(f"Error: {error_details.get('error', 'Unknown API error')}")
            if 'detail' in error_details:
                click.echo(f"Detail: {error_details['detail']}")
        except (json.JSONDecodeError, AttributeError):
            click.echo(f"Error canceling job: {e}")

def tail_job(job_id, project_config):
    """Tails the logs of a specific job.

    This function retrieves the latest log entries for a single job by its ID
    from the /job/{job_id}/tail/ endpoint. The log messages are then printed
    to the console.

    Args:
        job_id (int): The unique identifier for the job.
        project_config (dict): A dictionary containing the configuration for the
            active project, including the 'epic_api_url'.
    """
    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    try:
        response = requests.get(f"{api_url}/job/{job_id}/tail/", headers=headers)
        response.raise_for_status()
        log_data = response.json()
        log_events = log_data.get('logs', [])

        if not log_events:
            click.echo(f"No logs found for job {job_id}.")
            return

        click.echo(f"Logs for job {job_id}:")
        for log_event in log_events:
            timestamp = log_event.get('timestamp')
            message = log_event.get('message')
            click.echo(f"[{timestamp}] {message}")

    except requests.exceptions.RequestException as e:
        try:
            error_details = e.response.json()
            click.echo(f"Error: {error_details.get('error', 'Unknown API error')}")
            if 'detail' in error_details:
                click.echo(f"Detail: {error_details['detail']}")
        except (json.JSONDecodeError, AttributeError):
            click.echo(f"Error getting job logs: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")