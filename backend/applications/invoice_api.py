from flask import request, abort, send_file
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Partner, Transaction, Ticket, Visa, Service, Invoice
from datetime import datetime, timedelta
from io import BytesIO
import os
from fpdf import FPDF
from sqlalchemy import or_, and_ 
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
import tempfile
import xlsxwriter

# ========= Paths =========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_SAVE_DIR = os.path.join(BASE_DIR, 'invoices')
os.makedirs(PDF_SAVE_DIR, exist_ok=True)

HEADER_PATH = os.path.join(BASE_DIR, 'templates', 'header1.jpg')
FOOTER_PATH = os.path.join(BASE_DIR, 'templates', 'footer1.jpg')

# ========= Helpers =========
def generate_invoice_number(entity_type):
    year = datetime.now().year
    prefix_map = {
        'agent': f"{year}/A/INV/",
        'customer': f"{year}/C/INV/",
        'partner': f"{year}/P/INV/"
    }
    prefix = prefix_map.get(entity_type, f"{year}/X/INV/")
    
    last_invoice = Invoice.query.filter(
        Invoice.invoice_number.like(f"{prefix}%")
    ).order_by(Invoice.id.desc()).first()
    
    next_number = 1
    if last_invoice:
        try:
            # Extract just the numeric portion
            last_num = int(last_invoice.invoice_number.split('/')[-1])
            next_number = last_num + 1
        except ValueError:
            # Fallback if parsing fails
            next_number = 1
    
    return f"{prefix}{next_number:03d}"  # 3-digit format

def parse_date(date_input):
    if isinstance(date_input, (int, float)):
        # Convert timestamp to datetime
        return datetime.fromtimestamp(date_input / 1000).date()
    elif isinstance(date_input, str):
        try:
            # Try parsing as ISO format
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        except ValueError:
            pass
    elif isinstance(date_input, datetime):
        return date_input.date()
    
    raise ValueError(f"Invalid date format: {date_input}")

# ========= Core Logic =========
class PDF(FPDF):
    def header(self):
        if os.path.exists(HEADER_PATH):
            self.image(HEADER_PATH, x=0, y=0, w=self.w)
        self.set_y(50)
        
    def footer(self):
        self.set_y(-50)
        if os.path.exists(FOOTER_PATH):
            self.image(FOOTER_PATH, x=0, y=self.get_y(), w=self.w)

    def chapter_title(self, title, is_table_header=False):
        """Method to print chapter title and optionally set up for a table."""
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
        if is_table_header:
            self.set_fill_color(220, 220, 220) # Header background color
            
    def set_table_headers(self, headers, col_widths, font_size=9):
        """Store headers for repeating on new pages."""
        self.table_headers = headers
        self.table_col_widths = col_widths
        self.table_font_size = font_size
        
    def draw_table_headers(self):
        """Draws the stored table headers."""
        if not hasattr(self, 'table_headers'):
            return
        
        self.set_font('Arial', 'B', self.table_font_size)
        self.set_fill_color(220, 220, 220)
        
        for i, header in enumerate(self.table_headers):
            self.cell(self.table_col_widths[i], 8, header, 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', '', self.table_font_size - 1) # Normal font for rows

    def add_page(self, *args, **kwargs):
        """Override to add custom header logic."""
        super().add_page(*args, **kwargs)
        self.draw_table_headers()

class InvoiceCore:
    def _fetch_entity_data(self, entity_type, entity_id, start_date, end_date):
        entity_model = {
            'customer': Customer,
            'agent': Agent,
            'partner': Partner
        }.get(entity_type)

        if not entity_model:
            return None

        entity = entity_model.query.get(entity_id)
        if not entity:
            return None

        transactions = Transaction.query.filter(
            Transaction.date >= start_date,
            Transaction.date < end_date,
            Transaction.entity_type == entity_type,
            Transaction.entity_id == entity_id
        ).all()
        
        tickets = Ticket.query.filter(
            Ticket.date >= start_date,
            Ticket.date < end_date
        ).filter_by(**{f'{entity_type}_id': entity_id}).all()

        visas = Visa.query.filter(
            Visa.date >= start_date,
            Visa.date < end_date
        ).filter_by(**{f'{entity_type}_id': entity_id}).all()

        services = []
        if entity_type == 'customer':
            services = Service.query.filter(
                Service.date >= start_date,
                Service.date < end_date
            ).filter_by(customer_id=entity_id).all()
        
        credit_balance = 0.0
        if entity_type == 'customer':
            credit_balance = getattr(entity, 'credit_used', 0.0)
        elif entity_type == 'agent':
            credit_balance = getattr(entity, 'credit_balance', 0.0)
            
        return {
            "entity": {
                "name": entity.name,
                "type": entity_type,
                "contact": getattr(entity, 'contact', 'N/A'),
                "email": getattr(entity, 'email', 'N/A'),
                "address": getattr(entity, 'address', 'N/A'),
                "current_wallet_balance": getattr(entity, 'wallet_balance', 0.0),
                "current_credit_balance": credit_balance, 
                },
                "transactions": self._format_transactions(transactions),
                "tickets": self._format_bookings(tickets, 'ticket', entity_type),
                "visas": self._format_bookings(visas, 'visa', entity_type),
                "services": self._format_bookings(services, 'service', entity_type),
            }

    def _format_transactions(self, transactions):
        return [{
            "date": t.date.strftime('%Y-%m-%d'),
            "ref_no": t.ref_no,
            "type": t.transaction_type,
            "amount": t.amount,
            "description": t.description,
            "mode": t.mode,
        } for t in transactions]

    def _format_bookings(self, bookings, booking_type, entity_type):
        formatted_bookings = []
        for b in bookings:
            item = {
                "date": b.date.strftime('%Y-%m-%d'),
                "ref_no": b.ref_no,
                "type": booking_type,
                "status": b.status,
            }
            if entity_type == 'customer':
                item["Charge"] = b.customer_charge
                item["Paid"] = None
                item["Payment Mode"] = b.customer_payment_mode
                item["Refund Amount"] = b.customer_refund_amount if b.status == 'cancelled' else 0
            elif entity_type == 'agent':
                item["Charge"] = None
                item["Paid"] = b.agent_paid
                item["Payment Mode"] = b.agent_payment_mode
                item["Refund Amount"] = b.agent_recovery_amount if b.status == 'cancelled' else 0
            elif entity_type == 'partner':
                item["Charge"] = None
                item["Paid"] = b.partner_paid
                item["Payment Mode"] = b.partner_payment_mode
                item["Refund Amount"] = None
            
            formatted_bookings.append(item)
        return formatted_bookings

    def _generate_excel_data(self, data):
        """Generates a dictionary with all data structured for Excel export"""
        excel_data = {
            "Summary": {
                "headers": ["Key", "Value"],
                "data": [
                    ["Entity Name", data["entity"]["name"]],
                    ["Entity Type", data["entity"]["type"].capitalize()],
                    ["Contact", data["entity"]["contact"]],
                    ["Email", data["entity"]["email"]],
                    ["Current Wallet Balance", data["entity"]["current_wallet_balance"]],
                ]
            }
        }
        
        # Add credit balance based on entity type
        credit_label = "Current Credit Used" if data["entity"]["type"] == 'customer' else "Current Credit Balance"
        excel_data["Summary"]["data"].append([credit_label, data["entity"]["current_credit_balance"]])

        # Bookings section
        booking_headers = ["Date", "Ref No", "Description", "Amount", "Refund Amount", "Mode", "Status"]
        all_bookings = data['tickets'] + data['visas'] + data['services']
        
        booking_rows = []
        total_bookings_amount = 0
        total_refunds_amount = 0
        
        for item in all_bookings:
            amount_key = 'Charge' if data['entity']['type'] == 'customer' else 'Paid'
            amount = item.get(amount_key, 0)
            refund_amount = item.get("Refund Amount", 0)
            total_bookings_amount += amount
            total_refunds_amount += refund_amount
            
            row = [
                item['date'],
                item['ref_no'],
                f"{item['type'].capitalize()} Booking",
                amount,
                refund_amount,
                item.get('Payment Mode', '-').capitalize(),
                item['status'].capitalize()
            ]
            booking_rows.append(row)
            
        booking_rows.append(["", "", "Total Booked Amount:", total_bookings_amount, "", "", ""])
        booking_rows.append(["", "", "Total Refund Amount:", total_refunds_amount, "", "", ""])
        
        excel_data["Bookings"] = {
            "headers": booking_headers,
            "data": booking_rows
        }
        
        # Transactions section
        transactions_headers = ["Date", "Ref No", "Description", "Amount", "Mode"]
        transactions_rows = []
        total_receipts = 0
        total_payments = 0
        total_refunds = 0

        for item in data['transactions']:
            if item['type'] == 'receipt':
                total_receipts += item['amount']
            elif item['type'] == 'payment':
                total_payments += item['amount']
            elif item['type'] == 'refund':
                total_refunds += item['amount']
            
            row = [
                item['date'],
                item['ref_no'],
                f"{item['type'].replace('_', ' ').title()}",
                item['amount'],
                item['mode'].capitalize()
            ]
            transactions_rows.append(row)

        transactions_rows.append(["", "", "Total Receipts:", total_receipts, ""])
        transactions_rows.append(["", "", "Total Payments:", total_payments, ""])
        transactions_rows.append(["", "", "Total Refunds:", total_refunds, ""])
        
        excel_data["Transactions"] = {
            "headers": transactions_headers,
            "data": transactions_rows
        }

        return excel_data

    def _generate_invoice_pdf(self, data, entity_type, start_date, end_date, invoice_number=None, is_invoice=True):
        
        pdf = PDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=50)

        pdf.set_font('Arial', 'B', 20)
        if is_invoice:
            pdf.cell(0, 10, 'INVOICE', 0, 1, 'C')
        else:
            pdf.cell(0, 10, 'REPORT', 0, 1, 'C')
        pdf.ln(10)

        pdf.set_font('Arial', 'B', 12)
        if is_invoice and invoice_number:
            pdf.cell(0, 5, f'Invoice Number: {invoice_number}', 0, 1, 'L')
        
        pdf.cell(0, 5, f'Invoice To: {data["entity"]["name"]}', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f'Type: {entity_type.capitalize()}', 0, 1, 'L')
        pdf.cell(0, 5, f'Contact: {data["entity"]["contact"]}', 0, 1, 'L')
        pdf.cell(0, 5, f'Email: {data["entity"]["email"]}', 0, 1, 'L')
        pdf.ln(5)
        pdf.cell(0, 5, f'Date Range: {start_date} to {end_date}', 0, 1, 'L')

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, f'Current Wallet Balance: {data["entity"]["current_wallet_balance"]:.2f}', 0, 1, 'L')
        
        if entity_type == 'customer':
            pdf.cell(0, 5, f'Current Credit Used: {data["entity"]["current_credit_balance"]:.2f}', 0, 1, 'L')
        elif entity_type == 'agent':
            pdf.cell(0, 5, f'Current Credit Balance: {data["entity"]["current_credit_balance"]:.2f}', 0, 1, 'L')

        pdf.ln(10)
        
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Bookings for the period', 0, 1, 'L')
        
        booking_headers = ["Date", "Ref No", "Description", "Amount", "Refund Amount", "Mode", "Status"]
        booking_col_widths = [18, 25, 50, 25, 25, 25, 25]
        
        # Set and draw table headers for the first time
        pdf.set_table_headers(booking_headers, booking_col_widths)
        pdf.draw_table_headers() 
        
        pdf.set_font('Arial', '', 8)
        all_bookings = data['tickets'] + data['visas'] + data['services']
        
        total_bookings_amount = 0
        total_refunds_amount = 0
        
        booking_mode_totals = {'cash': 0, 'online': 0, 'wallet': 0}
        refund_mode_totals = {'cash': 0, 'online': 0, 'wallet': 0}
        
        for item in all_bookings:
            amount_key = 'Charge' if entity_type == 'customer' else 'Paid'
            amount = item.get(amount_key, 0)
            refund_amount = item.get("Refund Amount", 0)
            
            mode_key = item.get('Payment Mode', 'na').lower()
            if mode_key in booking_mode_totals:
                booking_mode_totals[mode_key] += amount
            
            total_bookings_amount += amount
            
            if item['status'] == 'cancelled':
                if mode_key in refund_mode_totals:
                    refund_mode_totals[mode_key] += refund_amount
                total_refunds_amount += refund_amount
            
            pdf.cell(booking_col_widths[0], 8, item['date'], 1, 0, 'C')
            pdf.cell(booking_col_widths[1], 8, item['ref_no'], 1, 0, 'C')
            pdf.cell(booking_col_widths[2], 8, f"{item['type'].capitalize()} Booking", 1, 0, 'L')
            
            if item['status'] == 'cancelled':
                pdf.cell(booking_col_widths[3], 8, f"{amount:.2f}", 1, 0, 'R')
                pdf.cell(booking_col_widths[4], 8, f"{refund_amount:.2f}", 1, 0, 'R')
            else:
                pdf.cell(booking_col_widths[3], 8, f"{amount:.2f}", 1, 0, 'R')
                pdf.cell(booking_col_widths[4], 8, '-', 1, 0, 'C')
                
            pdf.cell(booking_col_widths[5], 8, item.get('Payment Mode', '-').capitalize(), 1, 0, 'C')
            pdf.cell(booking_col_widths[6], 8, item['status'].capitalize(), 1, 0, 'C')
            pdf.ln()

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(sum(booking_col_widths) - 50, 8, 'Total Booked Amount:', 1, 0, 'R', 1)
        pdf.cell(50, 8, f"{total_bookings_amount:.2f}", 1, 0, 'R', 1)
        pdf.ln()
        
        pdf.cell(sum(booking_col_widths) - 50, 8, 'Total Refund Amount:', 1, 0, 'R', 1)
        pdf.cell(50, 8, f"{total_refunds_amount:.2f}", 1, 0, 'R', 1)
        pdf.ln()

        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, 'Booking Amounts by Mode:', 0, 1)
        for mode, total in booking_mode_totals.items():
            if total > 0:
                pdf.cell(0, 8, f"Total Paid via {mode.capitalize()}: {total:.2f}", 0, 1, 'R')

        pdf.ln(2)
        pdf.cell(0, 8, 'Refund Amounts by Mode:', 0, 1)
        for mode, total in refund_mode_totals.items():
            if total > 0:
                pdf.cell(0, 8, f"Total Refunded via {mode.capitalize()}: {total:.2f}", 0, 1, 'R')
        
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        
        cash_online_bookings = booking_mode_totals.get('cash', 0) + booking_mode_totals.get('online', 0)
        cash_online_refunds = refund_mode_totals.get('cash', 0) + refund_mode_totals.get('online', 0)
        net_amount_to_pay = cash_online_bookings - cash_online_refunds
        
        pdf.cell(0, 10, f"Net Booking Amount (Cash & Online): {net_amount_to_pay:.2f}", 0, 1, 'R')
        
        pdf.add_page()
        
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Transactions for the period', 0, 1, 'L')

        transactions_headers = ["Date", "Ref No", "Description", "Amount", "Mode"]
        transactions_col_widths = [20, 30, 70, 30, 40]
        
        # Set and draw table headers for the first time
        pdf.set_table_headers(transactions_headers, transactions_col_widths)
        pdf.draw_table_headers() 
        
        pdf.set_font('Arial', '', 9)
        total_receipts = 0
        total_payments = 0
        total_refunds = 0
        
        for item in data['transactions']:
            pdf.cell(transactions_col_widths[0], 8, item['date'], 1, 0, 'C')
            pdf.cell(transactions_col_widths[1], 8, item['ref_no'], 1, 0, 'C')
            pdf.cell(transactions_col_widths[2], 8, f"{item['type'].replace('_', ' ').title()}", 1, 0, 'L')
            pdf.cell(transactions_col_widths[3], 8, f"{item['amount']:.2f}", 1, 0, 'R')
            pdf.cell(transactions_col_widths[4], 8, item['mode'].capitalize(), 1, 0, 'C')
            pdf.ln()
            
            if item['type'] == 'receipt':
                total_receipts += item['amount']
            elif item['type'] == 'payment':
                total_payments += item['amount']
            elif item['type'] == 'refund':
                total_refunds += item['amount']
                
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"Total Receipts: {total_receipts:.2f}", 0, 1, 'R')
        pdf.cell(0, 8, f"Total Payments: {total_payments:.2f}", 0, 1, 'R')
        pdf.cell(0, 8, f"Total Refunds: {total_refunds:.2f}", 0, 1, 'R')
        pdf.ln(5)

        output = BytesIO()
        output.write(pdf.output(dest='S').encode('latin1'))
        output.seek(0)
        return output.getvalue()

    def apply_stamp(self, pdf_bytes, status):
        """Apply status stamp to PDF and return stamped bytes"""
        # Create watermark
        packet = BytesIO()
        can = canvas.Canvas(packet)
        
        # Set stamp properties based on status
        if status == 'paid':
            text = "PAID"
            color = (0, 0.5, 0)  # Green
        else:  # cancelled
            text = "CANCELLED"
            color = (0.8, 0, 0)  # Red
        
        # Draw transparent watermark
        can.setFont("Helvetica-Bold", 60)
        can.setFillColorRGB(*color, alpha=0.3)  # Transparent color
        can.saveState()
        can.translate(300, 400)  # Center of page
        can.rotate(45)  # Diagonal orientation
        can.drawString(-150, 0, text)
        can.restoreState()
        can.save()
        
        # Move to beginning of BytesIO buffer
        packet.seek(0)
        watermark = PdfReader(packet)
        watermark_page = watermark.pages[0]
        
        # Apply watermark to each page
        original = PdfReader(BytesIO(pdf_bytes))
        output = PdfWriter()
        
        for i in range(len(original.pages)):
            page = original.pages[i]
            page.merge_page(watermark_page)
            output.add_page(page)
        
        # Save watermarked PDF to BytesIO
        output_bytes = BytesIO()
        output.write(output_bytes)
        return output_bytes.getvalue()
    
# ========= API Resources =========
class InvoiceListResource(Resource, InvoiceCore):
    @check_permission()
    def get(self):
        status = request.args.get('status')
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        invoice_number = request.args.get('invoice_number')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = Invoice.query
        if status:
            query = query.filter(Invoice.status == status)
        if entity_type:
            query = query.filter(Invoice.entity_type == entity_type)
        if entity_id:
            query = query.filter(Invoice.entity_id == int(entity_id))
        if invoice_number:
            query = query.filter(Invoice.invoice_number.ilike(f"%{invoice_number}%"))
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Invoice.generated_date >= start_date, Invoice.generated_date < end_date)
            except ValueError:
                abort(400, "Invalid date format. Use YYYY-MM-DD.")

        invoices = query.order_by(Invoice.generated_date.desc()).all()
        result = []
        for inv in invoices:
            # Get entity name
            if inv.entity_type == 'customer':
                entity = Customer.query.get(inv.entity_id)
            elif inv.entity_type == 'agent':
                entity = Agent.query.get(inv.entity_id)
            elif inv.entity_type == 'partner':
                entity = Partner.query.get(inv.entity_id)
            else:
                entity = None
        
            result.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "entity_type": inv.entity_type,
                "entity_id": inv.entity_id,
                "entity_name": entity.name if entity else 'Unknown', 
                "period_start": inv.period_start.strftime('%Y-%m-%d'),
                "period_end": inv.period_end.strftime('%Y-%m-%d'),
                "status": inv.status,
                "generated_date": inv.generated_date.strftime('%Y-%m-%d'),
                "pdf_path": inv.pdf_path
            })
        return result
    
    @check_permission()
    def post(self): 
        data = request.get_json()
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        period_start_str = data.get('period_start')
        period_end_str = data.get('period_end')

        if not all([entity_type, entity_id, period_start_str, period_end_str]):
            abort(400, "Missing required fields.")
            
        try:
            period_start = datetime.strptime(period_start_str, '%Y-%m-%d').date()
            period_end = datetime.strptime(period_end_str, '%Y-%m-%d').date()
        except Exception as e:
            abort(400, f"Invalid date format: {str(e)}. Use YYYY-MM-DD.")

        # Check for existing overlapping invoices (only non-cancelled ones)
        existing = Invoice.query.filter(
            Invoice.entity_type == entity_type,
            Invoice.entity_id == entity_id,
            Invoice.status != 'cancelled',
            or_(
                and_(Invoice.period_start <= period_start, Invoice.period_end >= period_start),
                and_(Invoice.period_start <= period_end, Invoice.period_end >= period_end),
                and_(Invoice.period_start >= period_start, Invoice.period_end <= period_end)
            )
        ).first()

        if existing:
            abort(400, f"An active invoice already exists for this entity covering part of this period "
                   f"({existing.period_start} to {existing.period_end}). Please cancel it first.")

        entity_model = {'customer': Customer, 'agent': Agent, 'partner': Partner}.get(entity_type)
        entity = entity_model.query.get(entity_id)
        if not entity:
            abort(404, "Entity not found")

        # Generate invoice number by entity type
        invoice_number = generate_invoice_number(entity_type)

        data_dict = self._fetch_entity_data(
            entity_type, entity_id,
            datetime.combine(period_start, datetime.min.time()),
            datetime.combine(period_end, datetime.max.time())
        )
        if not data_dict:
            abort(404, "No data found for the selected entity and date range.")

        # Pass invoice_number to PDF generator
        pdf_bytes = self._generate_invoice_pdf(
            data_dict, 
            entity_type,
            period_start_str,
            period_end_str,
            invoice_number=invoice_number,
            is_invoice=True
        )

        # Create safe filename
        safe_filename = invoice_number.replace('/', '-') + '.pdf'
        
        entity_folder = os.path.join(PDF_SAVE_DIR, f"{entity_type}s")
        os.makedirs(entity_folder, exist_ok=True)

        pdf_path = os.path.join(entity_folder, safe_filename)
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)

        invoice = Invoice(
            invoice_number=invoice_number,
            entity_type=entity_type,
            entity_id=entity_id,
            period_start=period_start,
            period_end=period_end,
            status='pending',
            pdf_path=pdf_path
        )
        db.session.add(invoice)
        db.session.commit()

        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "entity_type": invoice.entity_type,
            "entity_id": invoice.entity_id,
            "period_start": invoice.period_start.strftime('%Y-%m-%d'),
            "period_end": invoice.period_end.strftime('%Y-%m-%d'),
            "status": invoice.status,
            "generated_date": invoice.generated_date.strftime('%Y-%m-%d'),
            "pdf_path": invoice.pdf_path
        }, 201

class InvoiceStatusResource(Resource, InvoiceCore):
    @check_permission()
    def patch(self, invoice_id):
        data = request.get_json()
        new_status = data.get('status')
        if new_status not in ['pending', 'paid', 'cancelled']:
            abort(400, "Invalid status.")

        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            abort(404, "Invoice not found.")

        old_status = invoice.status
        invoice.status = new_status
        
        if new_status in ['paid', 'cancelled'] and old_status != new_status:
            if not invoice.pdf_path or not os.path.exists(invoice.pdf_path):
                abort(404, "Invoice PDF not found.")
                
            with open(invoice.pdf_path, 'rb') as f:
                original_pdf = f.read()
            
            stamped_pdf = self.apply_stamp(original_pdf, new_status)
            
            with open(invoice.pdf_path, 'wb') as f:
                f.write(stamped_pdf)
        
        db.session.commit()
        return {"message": "Invoice status updated.", "status": new_status}

class InvoiceDownloadResource(Resource, InvoiceCore):
    @check_permission()
    def get(self, invoice_id):
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            abort(404, "Invoice not found.")
        if not invoice.pdf_path or not os.path.exists(invoice.pdf_path):
            abort(404, "Invoice PDF not found.")
        
        with open(invoice.pdf_path, 'rb') as f:
            original_pdf = f.read()
        
        if invoice.status in ['paid', 'cancelled']:
            stamped_pdf = self.apply_stamp(original_pdf, invoice.status)
            return send_file(
                BytesIO(stamped_pdf),
                as_attachment=True,
                download_name=f"{invoice.invoice_number}.pdf",
                mimetype="application/pdf"
            )
        
        return send_file(
            invoice.pdf_path,
            as_attachment=True,
            download_name=f"{invoice.invoice_number}.pdf",
            mimetype="application/pdf"
        )
    
class InvoiceDeleteResource(Resource):
    @check_permission()
    def delete(self, invoice_id):
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            abort(404, "Invoice not found.")

        if invoice.pdf_path and os.path.exists(invoice.pdf_path):
            try:
                os.remove(invoice.pdf_path)
            except OSError as e:
                print(f"Error deleting PDF file: {e}")

        db.session.delete(invoice)
        db.session.commit()
        return {"message": "Invoice deleted successfully."}, 200


class InvoiceExportResource(Resource, InvoiceCore):
    @check_permission()
    def post(self):
        data = request.get_json()
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        period_start_str = data.get('period_start')
        period_end_str = data.get('period_end')
        export_type = data.get('export_type')

        if not all([entity_type, entity_id, period_start_str, period_end_str, export_type]):
            abort(400, "Missing required fields.")

        try:
            period_start = datetime.strptime(period_start_str, '%Y-%m-%d').date()
            period_end = datetime.strptime(period_end_str, '%Y-%m-%d').date()
        except Exception:
            abort(400, "Invalid date format. Use YYYY-MM-DD.")
        
        data_dict = self._fetch_entity_data(
            entity_type, entity_id,
            datetime.combine(period_start, datetime.min.time()),
            datetime.combine(period_end, datetime.max.time())
        )
        if not data_dict:
            abort(404, "No data found for the selected entity and date range.")

        invoice_number = generate_invoice_number(entity_type)
        
        if export_type == 'pdf':
            pdf_bytes = self._generate_invoice_pdf(
                data_dict,
                entity_type,
                period_start_str,
                period_end_str,
                invoice_number=None,
                is_invoice=False
            )
            return send_file(
                BytesIO(pdf_bytes),
                as_attachment=True,
                download_name=f"{invoice_number.replace('/', '-')}-report.pdf",
                mimetype="application/pdf"
            )
        
        elif export_type == 'excel':
            excel_data = self._generate_excel_data(data_dict)
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})

            header_format = workbook.add_format({
                'bold': True,
                'font_size': 12,
                'bg_color': '#DDEBF7',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            currency_format = workbook.add_format({'num_format': '#,##0.00'})
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

            for sheet_name, sheet_content in excel_data.items():
                worksheet = workbook.add_worksheet(sheet_name)
                
                worksheet.write_row(0, 0, sheet_content['headers'], header_format)
                
                for row_num, row_data in enumerate(sheet_content['data'], start=1):
                    for col_num, value in enumerate(row_data):
                        header = sheet_content['headers'][col_num]
                        
                        if header == 'Date' and isinstance(value, str):
                            try:
                                # Convert the string to a datetime object
                                date_obj = datetime.strptime(value, '%Y-%m-%d')
                                worksheet.write_datetime(row_num, col_num, date_obj, date_format)
                            except ValueError:
                                worksheet.write(row_num, col_num, value) # Fallback to writing as string
                        elif sheet_name in ['Bookings', 'Transactions'] and header in ['Amount', 'Refund Amount', 'Total Booked Amount:', 'Total Refund Amount:', 'Total Receipts:', 'Total Payments:', 'Total Refunds:']:
                            worksheet.write(row_num, col_num, value, currency_format)
                        else:
                            worksheet.write(row_num, col_num, value)

                for col_num, header in enumerate(sheet_content['headers']):
                    max_len = max(len(str(header)), max((len(str(row[col_num])) for row in sheet_content['data'] if len(row) > col_num), default=0))
                    worksheet.set_column(col_num, col_num, max_len + 2)
            
            workbook.close()
            output.seek(0)
            
            return send_file(
                output,
                as_attachment=True,
                download_name=f"{invoice_number.replace('/', '-')}-report.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        else:
            abort(400, "Invalid export type.")