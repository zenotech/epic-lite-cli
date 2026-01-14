import click
import requests
import os
import json
import boto3
import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

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

def generate_spend_report(project_name, project_config, year=None, month=None):
    """Generates a PDF spend report using the EPIC API."""
    
    # Determine start and end dates
    now = datetime.datetime.now()
    if year and month:
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1)
        else:
            end_date = datetime.date(year, month + 1, 1)
    else:
        # Default to previous month
        # first day of current month
        end_date = datetime.date(now.year, now.month, 1)
        # first day of previous month
        if now.month == 1:
            start_date = datetime.date(now.year - 1, 12, 1)
        else:
            start_date = datetime.date(now.year, now.month - 1, 1)

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    click.echo(f"Generating report for period: {start_str} to {end_str}")

    token = os.environ.get("EPIC_API_TOKEN")
    if not token:
        click.echo("Error: EPIC_API_TOKEN environment variable not set. Please run 'epic init' first.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    api_url = project_config['epic_api_url']

    # Fetch Data from API
    try:
        params = {}
        if year:
            params['year'] = year
        if month:
            params['month'] = month

        response = requests.get(f"{api_url}/billing/cost", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])

    except requests.exceptions.RequestException as e:
        click.echo(f"Error querying EPIC API for billing data: {e}")
        return
    except json.JSONDecodeError:
        click.echo("Error: Failed to decode JSON response from server.")
        return

    # Process Data
    costs = []
    total_cost = 0.0
    
    if results:
        for result in results:
            for group in result['Groups']:
                service_name = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                if amount > 0: # Filter out zero costs
                    costs.append((service_name, amount))
                    total_cost += amount

    # Sort costs by amount descending
    costs.sort(key=lambda x: x[1], reverse=True)

    # Calculations
    service_charge = total_cost * 0.20
    net_total = total_cost + service_charge
    vat = net_total * 0.20
    grand_total = net_total + vat

    # PDF Generation
    filename = f"Spend_Report_{project_name}_{start_date.strftime('%Y_%m')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Logos
    # Attempt to locate logos relative to this file
    base_path = os.path.dirname(os.path.dirname(__file__)) # Up one level from epiccli
    
    logo_path = os.path.join(base_path, 'epiccli_ui', 'static', 'logo2.png')
    logo2_path = os.path.join(base_path, 'epiccli_ui', 'static', 'zenotech.png')

    def get_proportional_image(path, max_width, max_height, alignment='LEFT'):
        if not os.path.exists(path):
            return None
        try:
            img = ImageReader(path)
            iw, ih = img.getSize()
            aspect = ih / float(iw)
            
            # Determine dimensions based on constraints
            # Start by limited width
            width = min(iw, max_width)
            height = width * aspect
            
            # If height exceeds limit, scale down by height
            if height > max_height:
                height = max_height
                width = height / aspect
                
            return Image(path, width=width, height=height, hAlign=alignment)
        except Exception:
            return None

    logo_imgs = []
    
    # Left Logo (Max 5cm wide, 2.5cm high)
    img1 = get_proportional_image(logo_path, 5*cm, 2.5*cm, 'LEFT')
    if img1:
        logo_imgs.append(img1)
    
    # Right Logo (Max 5cm wide, 2.5cm high)
    img2 = get_proportional_image(logo2_path, 5*cm, 2.5*cm, 'RIGHT')
    if(img2):
        logo_imgs.append(img2)
        
    if len(logo_imgs) == 2:
        # Table with 2 columns to separate logos
        # Assuming A4 width (21cm) - Margins (~2.5cm*2) = ~16cm printable width
        logo_table = Table([[logo_imgs[0], logo_imgs[1]]], colWidths=[8*cm, 8*cm])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,0), 'LEFT'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(logo_table)
    elif len(logo_imgs) == 1:
        elements.append(logo_imgs[0])
    else:
        click.echo("Warning: Logos not found. Proceeding without logos.")

    elements.append(Spacer(1, 1*cm))
    
    # Title
    elements.append(Paragraph(f"Spend Report", styles['Title']))
    elements.append(Spacer(1, 0.5*cm))
    
    elements.append(Paragraph(f"<b>Period:</b> {start_str} to {end_str}", styles['Normal']))
    elements.append(Paragraph(f"<b>Project:</b> {project_name}", styles['Normal']))
    elements.append(Spacer(1, 1*cm))
    
    # Table Data
    data = [['Service', 'Cost (USD)']]
    for service, cost in costs:
        data.append([service, f"${cost:,.2f}"])
    
    data.append(['', '']) # Spacer row
    data.append(['Subtotal', f"${total_cost:,.2f}"])
    data.append(['Service Charge (20%)', f"${service_charge:,.2f}"])
    data.append(['Net Total', f"${net_total:,.2f}"])
    data.append(['VAT (20%)', f"${vat:,.2f}"])
    data.append(['Grand Total', f"${grand_total:,.2f}"])

    # Table Style
    t = Table(data, colWidths=[12*cm, 4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -6), 1, colors.black), # Grid for services
        ('LINEBELOW', (0, -6), (-1, -6), 2, colors.black), # Line after services
        ('FONTNAME', (0, -5), (-1, -1), 'Helvetica-Bold'), # Totals bold
    ]))
    
    elements.append(t)
    
    try:
        doc.build(elements)
        click.echo(f"Report generated successfully: {os.path.abspath(filename)}")
    except Exception as e:
        click.echo(f"Error generating PDF: {e}")