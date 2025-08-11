# In applications/ticket_api.py

from flask import request, abort, g
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Ticket, Particular, TravelLocation, Passenger
from datetime import datetime
from applications.pdf_excel_export_helpers import generate_export_excel, generate_export_pdf
from applications.common_booking_resource import CommonBookingResource

class TicketResource(Resource, CommonBookingResource):
    def __init__(self, **kwargs):
        super().__init__(model=Ticket, ref_prefix="T")
    
    @check_permission()
    def get(self):
        export_format = request.args.get('export')
        if export_format in ['excel', 'pdf']:
            # Correctly call the export method from the parent class
            return self.export_excel_pdf(self.MODEL, 'ticket')
        
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search_query', '')
        
        query = self.MODEL.query.options(db.joinedload(self.MODEL.customer), db.joinedload(self.MODEL.agent))

        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(self.MODEL.date.between(start, end))
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD.'}, 400
        
        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.outerjoin(Customer, self.MODEL.customer_id == Customer.id)\
                         .outerjoin(Agent, self.MODEL.agent_id == Agent.id)\
                         .filter(db.or_(
                            db.func.lower(self.MODEL.ref_no).like(search_pattern),
                            db.func.lower(Customer.name).like(search_pattern),
                            db.func.lower(Agent.name).like(search_pattern)
                         ))
        
        # Default sorting by reference number in descending order
        tickets = query.order_by(self.MODEL.ref_no.desc()).all()
        
        return [self._format_ticket(rec) for rec in tickets], 200

    @check_permission()
    def post(self, action=None):
        action = (action or request.args.get('action', '')).lower().strip()
        if action == 'cancel':
            return self.cancel_common_record(self.MODEL, request.json.get('ticket_id'), 'ticket')
        else:
            return self.book_record()

    @check_permission()
    def patch(self):
        data = request.json
        if not (record_id := data.get('id')):
            abort(400, "Missing ticket ID")
        
        # Pass 'ticket' as the ref_type
        return self.update_record(self.MODEL, record_id, 'ticket')

    @check_permission()
    def delete(self):
        if not (record_id := request.args.get('id')):
            abort(400, "Missing ticket ID")
            
        # Pass 'ticket' as the ref_type
        return self.delete_record(self.MODEL, record_id, 'ticket')

    # The following helper methods are specific to tickets and should be kept
    def book_record(self):
        data = request.json
        required = ['customer_id', 'travel_location_id', 'customer_charge', 'customer_payment_mode']
        if not all(field in data for field in required):
            abort(400, "Missing required fields")

        ticket_date = self._parse_ticket_date(data.get('date'))
        
        try:
            ticket = self.MODEL(
                customer_id=data['customer_id'],
                agent_id=data.get('agent_id'),
                travel_location_id=data['travel_location_id'],
                passenger_id=data.get('passenger_id'),
                ref_no=data.get('ref_no') or self._generate_reference_number(),
                status='booked',
                customer_charge=data['customer_charge'],
                agent_paid=data.get('agent_paid', 0),
                profit=data['customer_charge'] - data.get('agent_paid', 0),
                customer_payment_mode=data['customer_payment_mode'].lower().strip(),
                agent_payment_mode=data.get('agent_payment_mode', 'cash').lower().strip(),
                updated_by=getattr(g, 'username', 'system'),
                date=ticket_date,
                particular_id=data.get('particular_id')
            )
            db.session.add(ticket)
            db.session.flush()

            self._process_payments(ticket, 'book', 'ticket')

            db.session.commit()
            return {"message": "Ticket booked", "id": ticket.id, "ref_no": ticket.ref_no}, 201
        except Exception as e:
            db.session.rollback()
            abort(500, f"Booking failed: {str(e)}")

    def _format_ticket(self, ticket):
        return {
            'id': ticket.id,
            'ref_no': ticket.ref_no,
            'customer_id': ticket.customer_id,
            'customer_name': ticket.customer.name if ticket.customer else None,
            'agent_id': ticket.agent_id,
            'agent_name': ticket.agent.name if ticket.agent else None,
            'particular_id': ticket.particular_id,
            'travel_location_id': ticket.travel_location_id,
            'passenger_id': ticket.passenger_id,
            'customer_charge': ticket.customer_charge,
            'agent_paid': ticket.agent_paid,
            'profit': ticket.profit,
            'status': ticket.status,
            'date': ticket.date.isoformat() if ticket.date else None,
            'customer_payment_mode': ticket.customer_payment_mode,
            'agent_payment_mode': ticket.agent_payment_mode,
            'customer_refund_amount': ticket.customer_refund_amount,
            'customer_refund_mode': ticket.customer_refund_mode,
            'agent_recovery_amount': ticket.agent_recovery_amount,
            'agent_recovery_mode': ticket.agent_recovery_mode,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
            'updated_by': ticket.updated_by,
        }

    def _format_for_export(self, ticket):
        data = {
            'Reference No': ticket.ref_no,
            'Date': ticket.date.strftime('%Y-%m-%d') if ticket.date else '',
            'Customer': Customer.query.get(ticket.customer_id).name if ticket.customer_id else '',
            'Agent': Agent.query.get(ticket.agent_id).name if ticket.agent_id else '',
            'Particular': Particular.query.get(ticket.particular_id).name if ticket.particular_id else '',
            'Travel Location': TravelLocation.query.get(ticket.travel_location_id).name if ticket.travel_location_id else '',
            'Passenger': Passenger.query.get(ticket.passenger_id).name if ticket.passenger_id else '',
            'Customer Charge': ticket.customer_charge,
            'Agent Paid': ticket.agent_paid,
            'Profit': ticket.profit,
            'Status': ticket.status.capitalize(),
            'Customer Payment Mode': ticket.customer_payment_mode.capitalize(),
            'Agent Payment Mode': ticket.agent_payment_mode.capitalize() if ticket.agent_payment_mode else '',
        }
        
        if ticket.status == 'cancelled':
            data.update({
                'Customer Refund Amount': ticket.customer_refund_amount,
                'Customer Refund Mode': ticket.customer_refund_mode.capitalize(),
                'Agent Recovery Amount': ticket.agent_recovery_amount,
                'Agent Recovery Mode': ticket.agent_recovery_mode.capitalize() if ticket.agent_recovery_mode else '',
            })
            
        data.update({
            'Created At': ticket.created_at.strftime('%Y-%m-%d %H:%M'),
            'Updated At': ticket.updated_at.strftime('%Y-%m-%d %H:%M') if ticket.updated_at else '',
            'Updated By': ticket.updated_by
        })
        
        return data

    def _parse_ticket_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                abort(400, "Invalid date format. Use YYYY-MM-DD.")
        return datetime.now()

    def _generate_reference_number(self):
        current_year = datetime.now().year
        max_ref = db.session.query(db.func.max(self.MODEL.ref_no)).filter(
            self.MODEL.ref_no.like(f"{current_year}/T/%")
        ).scalar()
        last_num = int(max_ref.split('/')[-1]) if max_ref and '/' in max_ref else 0
        return f"{current_year}/T/{last_num + 1:05d}"