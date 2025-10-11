# In applications/ticket_api.py

from flask import request, abort, g
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Ticket, Particular, TravelLocation, Passenger, TicketType
from sqlalchemy import or_, func
from datetime import datetime, date, timedelta
from applications.pdf_excel_export_helpers import generate_export_excel, generate_export_pdf
from applications.common_booking_resource import CommonBookingResource

class TicketResource(Resource, CommonBookingResource):
    def __init__(self, **kwargs):
        super().__init__(model=Ticket, ref_prefix="T")
    
    def round_to_two(self, value):
        return round(float(value), 2) if value is not None else 0.0

    def _get_next_ref_no(self):
        current_year = datetime.now().year
        prefix = f"{current_year}/T/"
        max_ref = db.session.query(db.func.max(self.MODEL.ref_no)).filter(
            self.MODEL.ref_no.like(f"{prefix}%")
        ).scalar()
        last_num = int(max_ref.split('/')[-1]) if max_ref and '/' in max_ref else 0
        return f"{prefix}{last_num + 1:05d}"
    
    @check_permission()
    def get(self):
        # Handle the next reference number endpoint first
        if request.path.endswith('/next_ref_no'):
            return {'ref_no': self._get_next_ref_no()}, 200

        # Original GET logic for fetching tickets
        export_format = request.args.get('export')
        status = request.args.get('status')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        search_query = request.args.get('search_query', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort_by', 'ref_no')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Eager-load related models
        query = self.MODEL.query.options(
            db.joinedload(self.MODEL.customer),
            db.joinedload(self.MODEL.agent),
            db.joinedload(self.MODEL.passenger),
            db.joinedload(self.MODEL.ticket_type)
        )

        if status and status != 'all':
            query = query.filter(self.MODEL.status == status)

        if start_date_str and end_date_str:
            try:
                start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(self.MODEL.date.between(start, end))
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD.'}, 400
        
        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.outerjoin(Customer, self.MODEL.customer_id == Customer.id)\
                         .outerjoin(Agent, self.MODEL.agent_id == Agent.id)\
                         .outerjoin(Passenger, self.MODEL.passenger_id == Passenger.id)\
                         .outerjoin(TicketType, self.MODEL.ticket_type_id == TicketType.id)\
                         .filter(or_(
                            func.lower(self.MODEL.ref_no).like(search_pattern),
                            func.lower(Customer.name).like(search_pattern),
                            func.lower(Agent.name).like(search_pattern),
                            func.lower(Passenger.name).like(search_pattern),
                            func.lower(TicketType.name).like(search_pattern),
                         ))
        
        if sort_by in ['ref_no', 'date', 'customer_name', 'passenger_name', 'agent_name', 'agent_paid', 'customer_charge', 'profit', 'ticket_type_name']:
            if sort_by in ['customer_name', 'agent_name', 'passenger_name', 'ticket_type_name']:
                sort_model = {
                    'customer_name': Customer,
                    'agent_name': Agent,
                    'passenger_name': Passenger,
                    'ticket_type_name': TicketType,
                }.get(sort_by)
                if sort_model:
                    sort_column = getattr(sort_model, 'name')
                    if sort_order == 'ascend':
                        query = query.order_by(sort_column.asc())
                    else:
                        query = query.order_by(sort_column.desc())
            else:
                sort_column = getattr(self.MODEL, sort_by)
                if sort_order == 'ascend':
                    query = query.order_by(sort_column.asc())
                else:
                    query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(self.MODEL.ref_no.desc())
            
        if export_format in ['excel', 'pdf']:
            tickets = query.all()
            formatted_data = [self._format_for_export(rec) for rec in tickets]
            if export_format == 'excel':
                return generate_export_excel(formatted_data, 'ticket')
            if export_format == 'pdf':
                title = f"{status.capitalize()} Tickets"
                return generate_export_pdf(formatted_data, title, start_date_str, end_date_str, status='ticket')

        paginated_result = query.paginate(page=page, per_page=per_page, error_out=False)
        tickets = paginated_result.items
        
        return {
            'data': [self._format_ticket(rec) for rec in tickets],
            'total': paginated_result.total,
            'page': paginated_result.page,
            'per_page': paginated_result.per_page
        }, 200

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
        
        return self.update_record(self.MODEL, record_id, 'ticket')

    @check_permission()
    def delete(self):
        if not (record_id := request.args.get('id')):
            abort(400, "Missing ticket ID")
            
        return self.delete_record(self.MODEL, record_id, 'ticket')

    def book_record(self):
        data = request.json
        required = ['customer_id', 'travel_location_id', 'customer_charge', 'customer_payment_mode', 'ticket_type_id']
        if not all(field in data for field in required):
            abort(400, "Missing required fields")

        ticket_date = self._parse_date(data.get('date'))
        
        try:
            customer_charge = float(data['customer_charge'])
            agent_paid = float(data.get('agent_paid', 0))

            ticket = self.MODEL(
                customer_id=data['customer_id'],
                agent_id=data.get('agent_id'),
                travel_location_id=data['travel_location_id'],
                passenger_id=data.get('passenger_id'),
                ref_no=data.get('ref_no') or self._get_next_ref_no(),
                status='booked',
                ticket_type_id=data['ticket_type_id'],
                customer_charge = self.round_to_two(data['customer_charge']),
                agent_paid=agent_paid,
                profit=round(customer_charge - agent_paid, 2),
                customer_payment_mode=data['customer_payment_mode'].lower().strip(),
                agent_payment_mode=data.get('agent_payment_mode', 'cash').lower().strip(),
                updated_by=getattr(g, 'username', 'system'),
                date=ticket_date,
                particular_id=data.get('particular_id'),
                description=data.get('description')
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
            'passenger_name': ticket.passenger.name if ticket.passenger else None,
            'passenger_first_name': ticket.passenger.first_name if ticket.passenger else None,
            'passenger_middle_name': ticket.passenger.middle_name if ticket.passenger else None,
            'passenger_last_name': ticket.passenger.last_name if ticket.passenger else None,
            'ticket_type_id': ticket.ticket_type_id,
            'ticket_type_name': ticket.ticket_type.name if ticket.ticket_type else None,
            'customer_charge': ticket.customer_charge,
            'agent_paid': ticket.agent_paid,
            'profit': ticket.profit,
            'status': ticket.status,
            'date': ticket.date.isoformat() if ticket.date else None,
            'description': ticket.description,
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
            'Customer': ticket.customer.name if ticket.customer else '',
            'Agent': ticket.agent.name if ticket.agent else '',
            'Particular': ticket.particular.name if ticket.particular else '',
            'Travel Location': ticket.travel_location.name if ticket.travel_location else '',
            'Passenger First Name': ticket.passenger.first_name if ticket.passenger else '',
            'Passenger Middle Name': ticket.passenger.middle_name if ticket.passenger else '',
            'Passenger Last Name': ticket.passenger.last_name if ticket.passenger else '',
            'Ticket Type': ticket.ticket_type.name if ticket.ticket_type else '',
            'Customer Charge': ticket.customer_charge,
            'Agent Paid': ticket.agent_paid,
            'Profit': ticket.profit,
            'Status': ticket.status.capitalize(),
            'Customer Payment Mode': ticket.customer_payment_mode.capitalize(),
            'Agent Payment Mode': ticket.agent_payment_mode.capitalize() if ticket.agent_payment_mode else '',
            'Description': ticket.description if ticket.description else '',
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

    def _parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                abort(400, "Invalid date format. Use YYYY-MM-DD.")
        return date.today()