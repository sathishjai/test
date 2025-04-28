#!/usr/bin/env python3
import os
import json
import argparse
from datetime import datetime
from weasyprint import HTML
from jinja2 import Template
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

# Initialize Flask app for the user input page
app = Flask(__name__)

def load_template(template_path):
    """Load HTML template from file"""
    try:
        with open(template_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: Template file not found at {template_path}")
        exit(1)

def load_customer_data(data_path=None):
    """Load customer data from JSON file or use provided data"""
    if data_path:
        try:
            with open(data_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Error: Customer data file not found at {data_path}")
            exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {data_path}")
            exit(1)
    else:
        # Return empty list if no data file provided
        return []

def generate_invoice_pdf(invoice_data, template_str):
    """Generate PDF invoice based on provided data"""
    # Create output directory if it doesn't exist
    if not os.path.exists('invoices'):
        os.makedirs('invoices')
    
    # Render HTML template with invoice data
    template = Template(template_str)
    rendered_html = template.render(**invoice_data)
    
    # Create sanitized filename
    sanitized_name = invoice_data['client_name'].replace(' ', '_').replace('/', '_').replace('\\', '_')
    output_filename = f"invoices/invoice_{invoice_data['invoice_no']}.pdf"
    
    # Convert HTML to PDF
    HTML(string=rendered_html).write_pdf(output_filename)
    
    return output_filename

def calculate_totals(invoice_data):
    """Calculate subtotal, total, and balance due"""
    # Calculate subtotal from items
    subtotal = sum(item['amount'] for item in invoice_data['items'])
    invoice_data['subtotal'] = subtotal
    
    # Calculate total (add tax if needed)
    invoice_data['total'] = subtotal
    
    # Calculate balance due
    invoice_data['balance_due'] = invoice_data['total'] - invoice_data['paid_amount']
    
    return invoice_data

def process_invoice_data(invoice_data, template_str):
    """Process invoice data and generate PDF"""
    print("Generating invoice...")
    
    # Calculate totals
    invoice_data = calculate_totals(invoice_data)
    
    # Generate PDF
    output_file = generate_invoice_pdf(invoice_data, template_str)
    print(f"Created: {output_file}")
    
    return output_file

def run_command_line():
    parser = argparse.ArgumentParser(description='Generate PDF invoices from invoice data')
    parser.add_argument('--template', default='invoice_template.html', help='Path to HTML template file')
    parser.add_argument('--data', help='Path to JSON file with invoice data')
    parser.add_argument('--web', action='store_true', help='Run web interface for invoice generation')
    
    # Check if no arguments were provided
    import sys
    if len(sys.argv) == 1:
        # If no arguments provided, show help and then run the web interface
        parser.print_help()
        print("\nStarting web interface as no arguments were provided...")
        app.run(debug=True)
        return
    
    args = parser.parse_args()
    
    if args.web:
        app.run(debug=True)
        return
    
    # Load template
    template_str = load_template(args.template)
    
    # Load data from file if provided
    if args.data:
        try:
            # Check if data is a list or single object
            invoice_data = load_customer_data(args.data)
            if isinstance(invoice_data, list):
                for data in invoice_data:
                    process_invoice_data(data, template_str)
                print("All invoices generated successfully!")
            else:
                process_invoice_data(invoice_data, template_str)
                print("Invoice generated successfully!")
        except Exception as e:
            print(f"Error processing invoice data: {e}")
    else:
        print("No invoice data provided. Use --data option or run with --web for web interface.")
        parser.print_help()

# Flask routes for web interface
@app.route('/')
def index():
    try:
        return render_template('input_form.html')
    except Exception as e:
        # Check if templates directory exists
        if not os.path.exists('templates'):
            os.makedirs('templates')
            print("Created 'templates' directory. Please place input_form.html in this directory.")
        
        # Return a basic HTML page with instructions
        return """
        <html>
        <head><title>Invoice Generator</title></head>
        <body>
            <h1>Invoice Generator Setup</h1>
            <p>The template directory is missing or the input form template is not found.</p>
            <p>Please ensure you have set up the following directory structure:</p>
            <pre>
            invoice_project/
            ├── invoice_generator.py
            ├── invoice_template.html
            └── templates/
                └── input_form.html
            </pre>
            <p>Please check the console for more information.</p>
        </body>
        </html>
        """

def save_invoice_to_json(invoice_data):
    """Save invoice data to a JSON file"""
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # Path to the JSON file
    json_file = 'data/invoices.json'
    
    # Load existing data if file exists
    existing_data = []
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as file:
                existing_data = json.load(file)
        except json.JSONDecodeError:
            # If file is corrupted, start with empty list
            existing_data = []
    
    # Add timestamp to invoice data
    invoice_data['saved_timestamp'] = datetime.now().isoformat()
    
    # Append new invoice data
    existing_data.append(invoice_data)
    
    # Save updated data back to file
    with open(json_file, 'w') as file:
        json.dump(existing_data, file, indent=4)
    
    return json_file

@app.route('/generate', methods=['POST'])
def generate():
    try:
        # Extract form data
        invoice_data = {
            'company_name': request.form['company_name'],
            'company_address': request.form['company_address'],
            'company_city': request.form['company_city'],
            'company_zip': request.form['company_zip'],
            'company_phone': request.form['company_phone'],
            'company_email': request.form['company_email'],
            
            'client_name': request.form['client_name'],
            'client_address': request.form['client_address'],
            'client_city': request.form['client_city'],
            'client_country': request.form['client_country'],
            
            'invoice_no': request.form['invoice_no'],
            'invoice_date': request.form['invoice_date'],
            'due_date': request.form['due_date'],
            
            'items': [],
            'paid_amount': float(request.form['paid_amount']),
            'payment_instructions': request.form['payment_instructions'],
            'paid_date': request.form['paid_date']
        }
        
        # Extract items (increasing to 20 items)
        item_count = 0
        for i in range(1, 21):  # Increased from 10 to 20 items
            if f'item_description_{i}' in request.form and request.form[f'item_description_{i}']:
                item = {
                    'no': i,
                    'description': request.form[f'item_description_{i}'],
                    'quantity': int(request.form[f'item_qty_{i}']),
                    'rate': float(request.form[f'item_rate_{i}']),
                    'amount': float(request.form[f'item_qty_{i}']) * float(request.form[f'item_rate_{i}'])
                }
                invoice_data['items'].append(item)
                item_count += 1
        
        # Save invoice data to JSON file
        json_file = save_invoice_to_json(invoice_data)
        print(f"Invoice data saved to {json_file}")
        
        # Load template
        template_str = load_template('invoice_template.html')
        
        # Generate PDF
        output_file = process_invoice_data(invoice_data, template_str)
        
        # Return the PDF or a success message with download link
        directory = os.path.dirname(output_file)
        filename = os.path.basename(output_file)
        return redirect(url_for('download_file', filename=filename))
    
    except Exception as e:
        return f"""
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error Generating Invoice</h1>
            <p>An error occurred: {str(e)}</p>
            <p><a href="/">Go back to form</a></p>
        </body>
        </html>
        """

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('invoices', filename, as_attachment=True)

if __name__ == "__main__":
    run_command_line()