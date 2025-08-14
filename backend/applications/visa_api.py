# applications/visa_api.py

from flask import request, abort, g
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Visa, Particular, TravelLocation, Passenger, VisaType
from datetime import datetime, date, timedelta
from applications.common_booking_resource import CommonBookingResource
from applications.pdf_excel_export_helpers import generate_export_excel, generate_export_pdf

class VisaResource(Resource, CommonBookingResource):
    def __init__(self, **kwargs):
        super().__init__(model=Visa, ref_prefix="V")
    def round_to_two(self, value):
        return round(float(value), 2) if value is not None else 0.0
    
    @check_permission()
    def get(self):
        export_format = request.args.get('export')
        status = request.args.get('status')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        search_query = request.args.get('search_query', '')

        # Eager-load all related models
        query = self.MODEL.query.options(
            db.joinedload(self.MODEL.customer),
            db.joinedload(self.MODEL.agent),
            db.joinedload(self.MODEL.visa_type)
        )

        # Filter by status if specified
        if status and status != 'all':
            query = query.filter(self.MODEL.status == status)

        # Filter by date range
        if start_date_str and end_date_str:
            try:
                start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(self.MODEL.date.between(start, end))
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD.'}, 400

        # Filter by search query, joining on all relevant tables
        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.outerjoin(Customer, self.MODEL.customer_id == Customer.id)\
                         .outerjoin(Agent, self.MODEL.agent_id == Agent.id)\
                         .outerjoin(VisaType, self.MODEL.visa_type_id == VisaType.id)\
                         .filter(db.or_(
                            db.func.lower(self.MODEL.ref_no).like(search_pattern),
                            db.func.lower(Customer.name).like(search_pattern),
                            db.func.lower(Agent.name).like(search_pattern),
                            db.func.lower(VisaType.name).like(search_pattern)
                         ))

        # Apply default descending sort order
        visas = query.order_by(self.MODEL.ref_no.desc()).all()
        
        if export_format in ['excel', 'pdf']:
            formatted_data = [self._format_for_export(rec) for rec in visas]
            if export_format == 'excel':
                return generate_export_excel(formatted_data, 'visa')
            if export_format == 'pdf':
                title = f"{status.capitalize()} Visas"
                return generate_export_pdf(formatted_data, title, start_date_str, end_date_str, status='visa')

        return [self._format_visa(rec) for rec in visas], 200

    @check_permission()
    def post(self, action=None):
        action = (action or request.args.get('action', '')).lower().strip()
        if action == 'cancel':
            return self.cancel_common_record(self.MODEL, request.json.get('visa_id'), 'visa')
        else:
            return self.book_record()

    @check_permission()
    def patch(self):
        data = request.json
        record_id = data.get('id')
        if not record_id:
            abort(400, "Missing visa ID")
        # Pass 'visa' as the ref_type
        return self.update_record(self.MODEL, record_id, 'visa')

    @check_permission()
    def delete(self):
        record_id = request.args.get('id')
        if not record_id:
            abort(400, "Missing visa ID")
        # Pass 'visa' as the ref_type
        return self.delete_record(self.MODEL, record_id, 'visa')

    # The following helper methods are specific to visas and should be kept
    def book_record(self):
        data = request.json
        required_fields = ['customer_id', 'travel_location_id', 'visa_type_id', 'customer_charge', 'customer_payment_mode']
        if not all(field in data for field in required_fields):
            abort(400, "Missing required fields")

        visa_date = self._parse_date(data.get('date'))
        
        try:
            customer_charge = float(data['customer_charge'])
            agent_paid = float(data.get('agent_paid', 0))

            visa = self.MODEL(
                customer_id=data['customer_id'],
                agent_id=data.get('agent_id'),
                travel_location_id=data['travel_location_id'],
                passenger_id=data.get('passenger_id'),
                visa_type_id=data['visa_type_id'],
                ref_no=data.get('ref_no') or self._generate_reference_number(),
                status='booked',
                customer_charge = self.round_to_two(data['customer_charge']),
                agent_paid=agent_paid,
                # Correctly calculate and round profit
                profit=round(customer_charge - agent_paid, 2),
                customer_payment_mode=data['customer_payment_mode'].lower().strip(),
                agent_payment_mode=data.get('agent_payment_mode', 'wallet').lower().strip(),
                updated_by=getattr(g, 'username', 'system'),
                created_at=datetime.now(),
                date=visa_date,
                particular_id=data.get('particular_id')
            )
            db.session.add(visa)
            db.session.flush()

            self._process_payments(visa, 'book', 'visa')
            db.session.commit()
            return {"message": "Visa booked", "id": visa.id, "ref_no": visa.ref_no}, 201
        except Exception as e:
            db.session.rollback()
            abort(500, f"Booking failed: {str(e)}")

    def _format_visa(self, visa):
        return {
            'id': visa.id,
            'ref_no': visa.ref_no,
            'visa_type_id': visa.visa_type_id,
            'visa_type': visa.visa_type.name if visa.visa_type else None,
            'customer_id': visa.customer_id,
            'customer_name': visa.customer.name if visa.customer else None,
            'agent_id': visa.agent_id,
            'agent_name': visa.agent.name if visa.agent else None,
            'particular_id': visa.particular_id,
            'travel_location_id': visa.travel_location_id,
            'passenger_id': visa.passenger_id,
            'passenger_name': visa.passenger.name if visa.passenger else None,
            'customer_charge': visa.customer_charge,
            'agent_paid': visa.agent_paid,
            'profit': visa.profit,
            'status': visa.status,
            'date': visa.date.isoformat() if visa.date else None,
            'customer_payment_mode': visa.customer_payment_mode,
            'agent_payment_mode': visa.agent_payment_mode,
            'customer_refund_amount': visa.customer_refund_amount,
            'customer_refund_mode': visa.customer_refund_mode,
            'agent_recovery_amount': visa.agent_recovery_amount,
            'agent_recovery_mode': visa.agent_recovery_mode,
            'created_at': visa.created_at.isoformat() if visa.created_at else None,
            'updated_at': visa.updated_at.isoformat() if visa.updated_at else None,
            'updated_by': visa.updated_by,
        }
        
    def _format_for_export(self, visa):
        data = {
            'Reference No': visa.ref_no,
            'Date': visa.date.strftime('%Y-%m-%d') if visa.date else '',
            'Customer': Customer.query.get(visa.customer_id).name if visa.customer_id else '',
            'Agent': Agent.query.get(visa.agent_id).name if visa.agent_id else '',
            'Particular': Particular.query.get(visa.particular_id).name if visa.particular_id else '',
            'Travel Location': TravelLocation.query.get(visa.travel_location_id).name if visa.travel_location_id else '',
            'Passenger': Passenger.query.get(visa.passenger_id).name if visa.passenger_id else '',
            'Visa Type': visa.visa_type.name if visa.visa_type else '',
            'Customer Charge': visa.customer_charge,
            'Agent Paid': visa.agent_paid,
            'Profit': visa.profit,
            'Status': visa.status.capitalize(),
            'Customer Payment Mode': visa.customer_payment_mode.capitalize(),
            'Agent Payment Mode': visa.agent_payment_mode.capitalize() if visa.agent_payment_mode else '',
        }
        
        if visa.status == 'cancelled':
            data.update({
                'Customer Refund Amount': visa.customer_refund_amount,
                'Customer Refund Mode': visa.customer_refund_mode.capitalize(),
                'Agent Recovery Amount': visa.agent_recovery_amount,
                'Agent Recovery Mode': visa.agent_recovery_mode.capitalize() if visa.agent_recovery_mode else '',
            })
            
        data.update({
            'Created At': visa.created_at.strftime('%Y-%m-%d %H:%M'),
            'Updated At': visa.updated_at.strftime('%Y-%m-%d %H:%M') if visa.updated_at else '',
            'Updated By': visa.updated_by
        })
        
        return data

    def _parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                abort(400, "Invalid date format. Use YYYY-MM-DD.")
        return date.today()

    def _generate_reference_number(self):
        current_year = datetime.now().year
        prefix = f"{current_year}/V/"
        max_ref = db.session.query(db.func.max(self.MODEL.ref_no)).filter(self.MODEL.ref_no.like(f"{prefix}%")).scalar()
        last_num = int(max_ref.split('/')[-1]) if max_ref else 0
        return f"{prefix}{last_num + 1:05d}"