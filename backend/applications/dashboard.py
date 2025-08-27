from flask_restful import Resource
from flask import jsonify, request, send_file
from datetime import datetime, timedelta
from sqlalchemy import func, case, and_, or_, union_all, select
from io import BytesIO
from fpdf import FPDF

from .model import db, CompanyAccountBalance, Ticket, Transaction, Service, Particular, Agent, Customer, Partner, Visa


# Helper function to get dashboard metrics data (reused by API and PDF export)
def _get_dashboard_metrics_data(start_date_str, end_date_str):
    if not start_date_str or not end_date_str:
        raise ValueError("start_date and end_date are required.")

    start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    # Base query filter for date range, using func.date() for robustness
    transaction_date_filter = and_(func.date(Transaction.date) >= start_date_obj, func.date(Transaction.date) <= end_date_obj)
    service_date_filter = and_(func.date(Service.date) >= start_date_obj, func.date(Service.date) <= end_date_obj)
    ticket_date_filter = and_(func.date(Ticket.date) >= start_date_obj, func.date(Ticket.date) <= end_date_obj)
    visa_date_filter = and_(func.date(Visa.date) >= start_date_obj, func.date(Visa.date) <= end_date_obj)

    # --- Fetch current company balances up to the end of the selected end_date_str ---
    # Reverting to fetch the latest value from the DB, ignoring date range
    cash_balance_obj = CompanyAccountBalance.query.filter_by(mode='cash') \
                                            .order_by(CompanyAccountBalance.updated_at.desc(), CompanyAccountBalance.id.desc()) \
                                            .first()
    cash_balance = cash_balance_obj.balance if cash_balance_obj else 0.0

    online_balance_obj = CompanyAccountBalance.query.filter_by(mode='online') \
                                             .order_by(CompanyAccountBalance.updated_at.desc(), CompanyAccountBalance.id.desc()) \
                                             .first()
    online_balance = online_balance_obj.balance if online_balance_obj else 0.0
    # --- End Company Balance Fetch ---

    # 1. Cumulative Sales of Tickets and Visas
    # Subquery for booked tickets
    booked_tickets = select(
        Ticket.customer_charge.label('customer_charge'),
        Ticket.agent_paid.label('agent_paid')
    ).filter(ticket_date_filter, Ticket.status == 'booked')

    # Subquery for booked visas
    booked_visas = select(
        Visa.customer_charge.label('customer_charge'),
        Visa.agent_paid.label('agent_paid')
    ).filter(visa_date_filter, Visa.status == 'booked')

    # Combine the booked data using union_all
    combined_sales_data = union_all(booked_tickets, booked_visas).alias('combined_sales_data')

    # Query the combined data for totals
    cumulative_sales = db.session.query(
        func.sum(combined_sales_data.c.customer_charge)
    ).scalar() or 0.0

    cumulative_agent_charges = db.session.query(
        func.sum(combined_sales_data.c.agent_paid)
    ).scalar() or 0.0

    profit_from_sales = cumulative_sales - cumulative_agent_charges

    # 2. Other Service Income
    other_service_income = db.session.query(func.sum(Service.customer_charge))\
                           .filter(service_date_filter, Service.status == 'booked')\
                           .scalar() or 0.0

    # 3. Expenditure (other than customer/partner/agent cash_deposit, not wallet updated amount)
    total_expenditure = db.session.query(func.sum(Transaction.amount))\
                            .filter(
                                transaction_date_filter,
                                Transaction.transaction_type == 'payment',
                                Transaction.pay_type != 'wallet_transfer',
                                or_(
                                    Transaction.entity_type == 'others',
                                    and_(
                                        Transaction.entity_type == 'agent',
                                        Transaction.pay_type == 'other_expense',
                                        Transaction.extra_data.cast(db.String).like('%"deduct_from_account": true%')
                                    ),
                                    and_(
                                        or_(Transaction.entity_type == 'customer', Transaction.entity_type == 'partner'),
                                        or_(
                                            Transaction.pay_type == 'cash_withdrawal',
                                            and_(
                                                Transaction.pay_type == 'other_expense',
                                                Transaction.extra_data.cast(db.String).like('%"deduct_from_account": true%')
                                            )
                                        )
                                    )
                                )
                            )\
                            .scalar() or 0.0

    # 4. Net profit
    net_profit = profit_from_sales + other_service_income - total_expenditure

    # 5. Total Agent Deposits
    total_agent_deposit = db.session.query(func.sum(Transaction.amount))\
                         .filter(
                             transaction_date_filter,
                             Transaction.entity_type == 'agent',
                             or_(
                                 and_(Transaction.transaction_type == 'receipt', Transaction.pay_type == 'cash_deposit'),
                                 and_(
                                     Transaction.transaction_type == 'receipt',
                                     Transaction.pay_type == 'other_receipt',
                                     Transaction.extra_data.cast(db.String).like('%"credit_to_account": true%')
                                 ),
                                 and_(Transaction.transaction_type == 'payment', Transaction.pay_type == 'cash_deposit')
                             )
                         )\
                         .scalar() or 0.0

    # 6. Total Customer Deposits
    total_customer_deposit = db.session.query(func.sum(Transaction.amount))\
                           .filter(
                               transaction_date_filter,
                               Transaction.entity_type == 'customer',
                               Transaction.transaction_type == 'receipt',
                               or_(
                                   Transaction.pay_type == 'cash_deposit',
                                   and_(
                                       Transaction.pay_type == 'other_receipt',
                                       Transaction.extra_data.cast(db.String).like('%"credit_to_account": true%')
                                   )
                               )
                           )\
                           .scalar() or 0.0

    # 7. Reverting to old logic: Total Agent Credit (actual credit used by agents)
    total_agent_credit = db.session.query(func.sum(Agent.credit_limit - Agent.credit_balance))\
                             .filter(Agent.active == True)\
                             .scalar() or 0.0

    # 8. Reverting to old logic: Total Customer Credit (actual credit used by customers)
    total_customer_credit = db.session.query(func.sum(Customer.credit_used))\
                                .filter(Customer.active == True)\
                                .scalar() or 0.0

    # 9. Total Cancelled Sales
    cancelled_tickets = select(Ticket.customer_charge.label('charge')).filter(
        ticket_date_filter, Ticket.status == 'cancelled'
    )
    cancelled_visas = select(Visa.customer_charge.label('charge')).filter(
        visa_date_filter, Visa.status == 'cancelled'
    )
    total_cancelled_sales = db.session.query(func.sum(union_all(cancelled_tickets, cancelled_visas).alias('combined_cancelled').c.charge)).scalar() or 0.0

    # 10. Total Refund to Customer (new logic)
    refund_status_filter = or_(Ticket.status == 'refunded', Ticket.status == 'cancelled')
    customer_refund_tickets = select(Ticket.customer_refund_amount.label('refund_amount')).filter(
        ticket_date_filter, refund_status_filter
    )
    refund_status_filter_visa = or_(Visa.status == 'refunded', Visa.status == 'cancelled')
    customer_refund_visas = select(Visa.customer_refund_amount.label('refund_amount')).filter(
        visa_date_filter, refund_status_filter_visa
    )
    total_customer_refund_amount = db.session.query(func.sum(union_all(customer_refund_tickets, customer_refund_visas).alias('combined_refunded').c.refund_amount)).scalar() or 0.0

    # 11. Total Refund to Agent (new logic)
    agent_refund_tickets = select(Ticket.agent_recovery_amount.label('refund_amount')).filter(
        ticket_date_filter, refund_status_filter
    )
    agent_refund_visas = select(Visa.agent_recovery_amount.label('refund_amount')).filter(
        visa_date_filter, refund_status_filter_visa
    )
    total_agent_refund_amount = db.session.query(func.sum(union_all(agent_refund_tickets, agent_refund_visas).alias('combined_refunded').c.refund_amount)).scalar() or 0.0


    # 12. Sales and Expense Trend Data for Chart (needs to be cumulative)
    daily_sales_tickets = select(
        func.date(Ticket.date).label('date'),
        func.sum(case((Ticket.status == 'booked', Ticket.customer_charge), else_=0)).label('daily_sales'),
        func.sum(case((Ticket.status == 'booked', Ticket.agent_paid), else_=0)).label('daily_expenses')
    ).filter(ticket_date_filter).group_by('date')
    
    daily_sales_visas = select(
        func.date(Visa.date).label('date'),
        func.sum(case((Visa.status == 'booked', Visa.customer_charge), else_=0)).label('daily_sales'),
        func.sum(case((Visa.status == 'booked', Visa.agent_paid), else_=0)).label('daily_expenses')
    ).filter(visa_date_filter).group_by('date')

    combined_daily_sales = union_all(daily_sales_tickets, daily_sales_visas).alias('combined_daily_sales')

    sales_expense_trend_query = db.session.query(
        combined_daily_sales.c.date,
        func.sum(combined_daily_sales.c.daily_sales).label('daily_sales'),
        func.sum(combined_daily_sales.c.daily_expenses).label('daily_expenses')
    ).group_by(combined_daily_sales.c.date).order_by(combined_daily_sales.c.date)
    
    sales_expense_trend = [{'date': row.date, 'sales': row.daily_sales, 'expenses': row.daily_expenses} for row in sales_expense_trend_query.all()]

    # 13. Sales by Particular for Bar Chart (needs to be cumulative)
    sales_by_particular_tickets = select(
        Particular.name,
        func.sum(Ticket.customer_charge).label('total_sales')
    ).join(Ticket, Ticket.particular_id == Particular.id).filter(ticket_date_filter, Ticket.status == 'booked').group_by(Particular.name)
    
    sales_by_particular_visas = select(
        Particular.name,
        func.sum(Visa.customer_charge).label('total_sales')
    ).join(Visa, Visa.particular_id == Particular.id).filter(visa_date_filter, Visa.status == 'booked').group_by(Particular.name)
    
    combined_particular_sales = union_all(sales_by_particular_tickets, sales_by_particular_visas).alias('combined_particular_sales')
    
    sales_by_particular_query = db.session.query(
        combined_particular_sales.c.name,
        func.sum(combined_particular_sales.c.total_sales).label('total_sales')
    ).group_by(combined_particular_sales.c.name).order_by(func.sum(combined_particular_sales.c.total_sales).desc())

    sales_by_particular_data = [{'name': row.name, 'sales': row.total_sales} for row in sales_by_particular_query.all()]

    # 14. Profit Breakdown by Particular for Pie Chart (needs to be cumulative)
    profit_by_particular_tickets = select(
        Particular.name,
        func.sum(Ticket.customer_charge - Ticket.agent_paid).label('total_profit')
    ).join(Ticket, Ticket.particular_id == Particular.id).filter(ticket_date_filter, Ticket.status == 'booked').group_by(Particular.name)
    
    profit_by_particular_visas = select(
        Particular.name,
        func.sum(Visa.customer_charge - Visa.agent_paid).label('total_profit')
    ).join(Visa, Visa.particular_id == Particular.id).filter(visa_date_filter, Visa.status == 'booked').group_by(Particular.name)

    combined_particular_profit = union_all(profit_by_particular_tickets, profit_by_particular_visas).alias('combined_particular_profit')
    
    profit_by_particular_query = db.session.query(
        combined_particular_profit.c.name,
        func.sum(combined_particular_profit.c.total_profit).label('total_profit')
    ).group_by(combined_particular_profit.c.name).order_by(func.sum(combined_particular_profit.c.total_profit).desc())

    profit_by_particular_data = [{'name': row.name, 'profit': row.total_profit} for row in profit_by_particular_query.all()]


    return {
        'cash_balance': cash_balance,
        'online_balance': online_balance,
        'total_sales': cumulative_sales,
        'total_agent_charges': cumulative_agent_charges,
        'profit_from_sales': profit_from_sales,
        'other_service_income': other_service_income,
        'total_expenditure': total_expenditure,
        'net_profit': net_profit,
        'total_agent_deposit': total_agent_deposit,
        'total_customer_deposit': total_customer_deposit,
        'total_agent_credit': total_agent_credit,
        'total_customer_credit': total_customer_credit,
        'total_cancelled_sales': total_cancelled_sales,
        'total_customer_refund_amount': total_customer_refund_amount,
        'total_agent_refund_amount': total_agent_refund_amount,
        'sales_expense_trend': sales_expense_trend,
        'sales_by_particular': sales_by_particular_data,
        'profit_by_particular': profit_by_particular_data
    }
class CompanyBalancesAPI(Resource):
    # This API is no longer necessary as the data is included in the main dashboard metrics API.
    # It can be removed to simplify the codebase.
    def get(self):
        # Existing code (kept for reference, but should be deprecated)
        end_date_str = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        try:
            balance_as_of_datetime = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(microseconds=1)
            cash_balance_obj = CompanyAccountBalance.query.filter_by(mode='cash') \
                                                    .filter(CompanyAccountBalance.updated_at <= balance_as_of_datetime) \
                                                    .order_by(CompanyAccountBalance.updated_at.desc(), CompanyAccountBalance.id.desc()) \
                                                    .first()
            cash_balance = cash_balance_obj.balance if cash_balance_obj else 0.0
            online_balance_obj = CompanyAccountBalance.query.filter_by(mode='online') \
                                                     .filter(CompanyAccountBalance.updated_at <= balance_as_of_datetime) \
                                                     .order_by(CompanyAccountBalance.updated_at.desc(), CompanyAccountBalance.id.desc()) \
                                                     .first()
            online_balance = online_balance_obj.balance if online_balance_obj else 0.0
            return {'cash_balance': cash_balance, 'online_balance': online_balance}
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to fetch company balances. Please check server logs.'}, 500


# Function to safely encode string for FPDF
def safe_encode(text):
    # Ensure text is string before encoding
    return str(text).encode('latin1', 'replace').decode('latin1')

# Generic helper for exporting lists of data to PDF
def _export_list_to_pdf(data_list, title, filename_prefix, column_headers):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(0, 10, safe_encode(title), 0, 1, 'C')
        pdf.ln(10)

        # Table setup
        if column_headers:
            page_width = pdf.w - 2 * pdf.l_margin
            col_width = page_width / len(column_headers)
            col_widths = [col_width] * len(column_headers)

            for i, header in enumerate(column_headers):
                if header == 'Name':
                    col_widths[i] = page_width * 0.20
                elif 'Balance' in header or 'Credit' in header or 'Limit' in header:
                    col_widths[i] = page_width * 0.15
                else:
                    col_widths[i] = page_width * 0.10
            
            total_calculated_width = sum(col_widths)
            if total_calculated_width > page_width:
                col_widths = [page_width / len(column_headers)] * len(column_headers)

        else:
            col_widths = []


        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(220, 220, 220)

        # Table Header
        for i, header in enumerate(column_headers):
            if i < len(col_widths):
                pdf.cell(col_widths[i], 10, safe_encode(header), 1, 0, 'C', True)
        pdf.ln()

        pdf.set_font("Arial", size=10)
        pdf.set_fill_color(255, 255, 255)

        # Table Rows
        for row_data in data_list:
            for i, header in enumerate(column_headers):
                if i < len(col_widths):
                    pdf.cell(col_widths[i], 10, safe_encode(str(row_data.get(header, ''))), 1, 0, 'L')
            pdf.ln()

        output = BytesIO()
        output.write(pdf.output(dest='S').encode('latin1'))
        output.seek(0)

        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        raise # Re-raise to be caught by the calling method


class DashboardMetricsAPI(Resource):
    # @check_permission()
    def get(self):
        export_format = request.args.get('export')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        try:
            metrics_data = _get_dashboard_metrics_data(start_date_str, end_date_str)

            if export_format == 'pdf':
                return self._export_pdf(metrics_data, start_date_str, end_date_str)
            else:
                return metrics_data
        except ValueError as ve:
            return {'error': str(ve)}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to fetch dashboard metrics or export PDF. Please check server logs.'}, 500

    def _export_pdf(self, metrics_data, start_date_str, end_date_str):
        """Helper method to generate and return the PDF file for Financial Overview."""
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            pdf.cell(0, 10, safe_encode("Financial Overview Dashboard Report"), 0, 1, 'C')
            pdf.ln(5)

            date_range_text = f"Date Range: {start_date_str} to {end_date_str}"
            pdf.cell(0, 10, safe_encode(date_range_text), 0, 1, 'C')
            pdf.ln(10)

            # Define data for PDF table
            data_for_pdf = [
                ["Metric", "Value"],
                ["Cash Balance (as of " + end_date_str + ")", f"{metrics_data.get('cash_balance', 0.0):.2f}"],
                ["Online Balance (as of " + end_date_str + ")", f"{metrics_data.get('online_balance', 0.0):.2f}"],
                ["Total Ticket Sales", f"{metrics_data['total_ticket_sales']:.2f}"],
                ["Total Agent Charges", f"{metrics_data['total_agent_charges']:.2f}"],
                ["Profit from Sales", f"{metrics_data['profit_from_sales']:.2f}"],
                ["Other Service Income", f"{metrics_data['other_service_income']:.2f}"],
                ["Total Expenditure", f"{metrics_data['total_expenditure']:.2f}"],
                ["Net Profit", f"{metrics_data['net_profit']:.2f}"],
                ["Total Agent Deposits", f"{metrics_data['total_agent_deposit']:.2f}"],
                ["Total Customer Deposits", f"{metrics_data['total_customer_deposit']:.2f}"],
                ["Total Agent Credit", f"{metrics_data['total_agent_credit']:.2f}"],
                ["Total Customer Credit", f"{metrics_data['total_customer_credit']:.2f}"]
            ]

            # Table setup
            col_widths = [80, 60]
            pdf.set_font("Arial", 'B', 10)
            pdf.set_fill_color(220, 220, 220)

            # Table Header
            for col_num, header in enumerate(data_for_pdf[0]):
                pdf.cell(col_widths[col_num], 10, safe_encode(header), 1, 0, 'C', True)
            pdf.ln()

            pdf.set_font("Arial", size=10)
            pdf.set_fill_color(255, 255, 255)

            # Table Rows
            for row in data_for_pdf[1:]:
                for col_num, cell_data in enumerate(row):
                    pdf.cell(col_widths[col_num], 10, safe_encode(str(cell_data)), 1, 0, 'L')
                pdf.ln()

            output = BytesIO()
            output.write(pdf.output(dest='S').encode('latin1'))
            output.seek(0)

            filename = f"financial_overview_{start_date_str}_to_{end_date_str}.pdf"
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            raise # Re-raise to be caught by the outer try-except in get()


class CustomerWalletCreditAPI(Resource):
    # @check_permission()
    def get(self):
        export_format = request.args.get('export')
        try:
            customers = Customer.query.filter_by(active=True).all()
            data = []
            for c in customers:
                data.append({
                    'ID': c.id,
                    'Name': c.name,
                    'Wallet Balance': c.wallet_balance,
                    'Credit Limit': c.credit_limit,
                    'Credit Used': c.credit_used,
                    'Credit Available': c.credit_limit - c.credit_used
                })

            if export_format == 'pdf':
                column_headers = ['ID', 'Name', 'Wallet Balance', 'Credit Limit', 'Credit Used', 'Credit Available']
                return _export_list_to_pdf(data, "Customer Wallet & Credit Balances", "customer_balances", column_headers)
            else:
                return jsonify(data)
        except Exception as e:
            return {'error': 'Failed to fetch customer wallet/credit data.'}, 500

class AgentWalletCreditAPI(Resource):
    # @check_permission()
    def get(self):
        export_format = request.args.get('export')
        try:
            agents = Agent.query.filter_by(active=True).all()
            data = []
            for a in agents:
                data.append({
                    'ID': a.id,
                    'Name': a.name,
                    'Wallet Balance': a.wallet_balance,
                    'Credit Limit': a.credit_limit,
                    'Credit Balance': a.credit_balance, # This is available credit
                    'Credit Used': a.credit_limit - a.credit_balance # Calculate used credit
                })

            if export_format == 'pdf':
                column_headers = ['ID', 'Name', 'Wallet Balance', 'Credit Limit', 'Credit Balance', 'Credit Used']
                return _export_list_to_pdf(data, "Agent Wallet & Credit Balances", "agent_balances", column_headers)
            else:
                return jsonify(data)
        except Exception as e:
            return {'error': 'Failed to fetch agent wallet/credit data.'}, 500

class PartnerWalletCreditAPI(Resource):
    # @check_permission()
    def get(self):
        export_format = request.args.get('export')
        try:
            partners = Partner.query.filter_by(active=True).all()
            data = []
            for p in partners:
                data.append({
                    'ID': p.id,
                    'Name': p.name,
                    'Wallet Balance': p.wallet_balance,
                    'Allow Negative Wallet': 'Yes' if p.allow_negative_wallet else 'No'
                })

            if export_format == 'pdf':
                column_headers = ['ID', 'Name', 'Wallet Balance', 'Allow Negative Wallet']
                return _export_list_to_pdf(data, "Partner Wallet Balances", "partner_balances", column_headers)
            else:
                return jsonify(data)
        except Exception as e:
            return {'error': 'Failed to fetch partner wallet data.'}, 500
