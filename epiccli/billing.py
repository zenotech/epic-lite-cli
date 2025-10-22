import click
import requests
import os
import json

def get_billing_info(project_config):
    """Fetches and displays billing information for the active project.

    This function retrieves the current monthly spend and the monthly spend limit
    from the EPIC API's /billing/limits endpoint. It uses the API URL from the
    provided project configuration and the authentication token from the
    EPIC_API_TOKEN environment variable.

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
        response = requests.get(f"{api_url}/billing/limits", headers=headers)
        response.raise_for_status()
        billing_data = response.json()

        click.echo("Billing Information:")
        monthly_spend = billing_data.get('monthly_spend', {'currency_symbol': '$', 'amount': 'N/A'})

        click.echo(f"  Monthly Spend to Date: {monthly_spend['currency_symbol']}{monthly_spend['amount']}")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error fetching billing information: {e}")
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")