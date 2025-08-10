# applications/reports_api.py
from flask import request, abort, send_file
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Partner, CompanyAccountBalance, Transaction, Ticket, Visa, Service
from datetime import datetime, timedelta
from applications.pdf_excel_export_helpers import generate_export_pdf, generate_export_excel
from io import BytesIO
import os
from fpdf import FPDF

# Assume a base URL for the project root to find the templates directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER_PATH = os.path.join(BASE_DIR, 'templates', 'header.jpg')
FOOTER_PATH = os.path.join(BASE_DIR, 'templates', 'footer.jpg')

class CompanyBalanceReportResource(Resource):
    @check_permission()
    def get(self, mode):
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        export_format = request.args.get('export')

        try:
            # Normalize to start-of-day and end-of-day
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
        except (ValueError, TypeError):
            abort(400, "Missing or invalid date range. Use YYYY-MM-DD format.")

        # We want the closing balance of the day before start_date
        prev_day_end = start_date - timedelta(seconds=1)

        # Get last entry for this mode before date range
        start_balance_entry = CompanyAccountBalance.query.filter_by(mode=mode)\
            .filter(CompanyAccountBalance.updated_at <= prev_day_end)\
            .order_by(CompanyAccountBalance.id.desc())\
            .first()

        # If no entry for this mode exists before the date range, balance is 0.0
        start_balance = start_balance_entry.balance if start_balance_entry else 0.0

        # Get entries for the selected mode within the range
        entries = CompanyAccountBalance.query.filter_by(mode=mode)\
            .filter(CompanyAccountBalance.updated_at >= start_date,
                    CompanyAccountBalance.updated_at <= end_date)\
            .order_by(CompanyAccountBalance.id.asc())\
            .all()

        # Prepare output data
        data = []
        for entry in entries:
            credited_amount = round(entry.credited_amount, 2) if entry.credited_amount > 0 else 0
            debited_amount = round(abs(entry.credited_amount), 2) if entry.credited_amount < 0 else 0

            data.append({
                "Ref No": entry.ref_no,
                "Date": entry.updated_at.strftime('%Y-%m-%d'),
                "Transaction Type": entry.transaction_type.replace('_', ' ').title(),
                "Action": entry.action.capitalize(),
                "Credit amount": credited_amount,
                "Debited amount": debited_amount,
                "Balance": round(entry.balance, 2)
            })

        # Determine ending balance
        end_balance = entries[-1].balance if entries else start_balance

        # Handle exports
        if export_format == 'excel':
            return generate_export_excel(data=data, status=f'{mode}_report')
        elif export_format == 'pdf':
            return generate_export_pdf(
                data=data,
                title=f"{mode.capitalize()} Account Report",
                date_range_start=start_date_str,
                date_range_end=end_date_str,
                summary_totals={"Opening Balance": start_balance, "Ending Balance": end_balance},
                exclude_columns=[],
                status=f'{mode}_report'
            )

        return {
            "entries": data,
            "starting_balance": round(start_balance, 2),
            "ending_balance": round(end_balance, 2)
        }, 200


class InvoiceResource(Resource):
    @check_permission()
    def get(self, entity_type, entity_id):
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not all([start_date_str, end_date_str]):
            abort(400, "Missing start_date or end_date parameter.")
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        except ValueError:
            abort(400, "Invalid date format. Use YYYY-MM-DD.")

        data = self._fetch_entity_data(entity_type, entity_id, start_date, end_date)
        
        if not data:
            abort(404, "No data found for the selected entity and date range.")

        pdf_bytes = self._generate_invoice_pdf(data, entity_type)

        return send_file(BytesIO(pdf_bytes), download_name="invoice.pdf", as_attachment=True, mimetype="application/pdf")

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

    def _generate_invoice_pdf(self, data, entity_type):
            class PDF(FPDF):
                def header(self):
                    if os.path.exists(HEADER_PATH):
                        self.image(HEADER_PATH, x=0, y=0, w=self.w)
                    self.set_y(50)
                    
                def footer(self):
                    self.set_y(-50)
                    if os.path.exists(FOOTER_PATH):
                        self.image(FOOTER_PATH, x=0, y=self.get_y(), w=self.w)
            
            pdf = PDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=50) # The bottom margin is now set to 50mm
            
            # --- Page 1: Bookings ---
            
            pdf.set_font('Arial', 'B', 20)
            pdf.cell(0, 10, 'INVOICE', 0, 1, 'C')
            pdf.ln(10)
            
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 5, f'Invoice To: {data["entity"]["name"]}', 0, 1, 'L')
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 5, f'Type: {entity_type.capitalize()}', 0, 1, 'L')
            pdf.cell(0, 5, f'Contact: {data["entity"]["contact"]}', 0, 1, 'L')
            pdf.cell(0, 5, f'Email: {data["entity"]["email"]}', 0, 1, 'L')
            pdf.ln(5)
            pdf.cell(0, 5, f'Date Range: {request.args.get("start_date")} to {request.args.get("end_date")}', 0, 1, 'L')
            
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
            
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(220, 220, 220)
            for i, header in enumerate(booking_headers):
                pdf.cell(booking_col_widths[i], 8, header, 1, 0, 'C', 1)
            pdf.ln()
            
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
                
                # Sum all bookings by their original amount and mode
                mode_key = item.get('Payment Mode', 'na').lower()
                if mode_key in booking_mode_totals:
                    booking_mode_totals[mode_key] += amount
                
                total_bookings_amount += amount
                
                # Sum refunds by mode and in total
                if item['status'] == 'cancelled':
                    if mode_key in refund_mode_totals:
                        refund_mode_totals[mode_key] += refund_amount
                    total_refunds_amount += refund_amount
                
                pdf.cell(booking_col_widths[0], 8, item['date'], 1, 0, 'C')
                pdf.cell(booking_col_widths[1], 8, item['ref_no'], 1, 0, 'C')
                pdf.cell(booking_col_widths[2], 8, f"{item['type'].capitalize()} Booking", 1, 0, 'L')
                
                # Display Amount and Refund Amount based on status
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

            # Display sums for each payment mode for bookings and refunds
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
            
            # --- Final Amount to Pay ---
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 12)
            
            # Calculate the net booking amount based on cash and online modes
            cash_online_bookings = booking_mode_totals.get('cash', 0) + booking_mode_totals.get('online', 0)
            cash_online_refunds = refund_mode_totals.get('cash', 0) + refund_mode_totals.get('online', 0)
            net_amount_to_pay = cash_online_bookings - cash_online_refunds
            
            pdf.cell(0, 10, f"Net Booking Amount (Cash & Online): {net_amount_to_pay:.2f}", 0, 1, 'R')
            
            # --- Page 2: Transactions ---
            pdf.add_page()
            
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Transactions for the period', 0, 1, 'L')

            transactions_headers = ["Date", "Ref No", "Description", "Amount", "Mode"]
            transactions_col_widths = [20, 30, 70, 30, 40]
            
            pdf.set_font('Arial', 'B', 10)
            pdf.set_fill_color(220, 220, 220)
            for i, header in enumerate(transactions_headers):
                pdf.cell(transactions_col_widths[i], 8, header, 1, 0, 'C', 1)
            pdf.ln()

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
            pdf.cell(0, 8, f"Net Transaction Amount: {(total_receipts - total_payments - total_refunds):.2f}", 0, 1, 'R')

            output = BytesIO()
            output.write(pdf.output(dest='S').encode('latin1'))
            output.seek(0)
            return output.getvalue()