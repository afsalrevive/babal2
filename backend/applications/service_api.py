# applications/service_api.py
from flask import request, abort, g
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Particular, Service, CompanyAccountBalance
from datetime import datetime, timedelta, date
from applications.pdf_excel_export_helpers import generate_export_pdf, generate_export_excel

class ServiceResource(Resource):
    def __init__(self, **kwargs):
        super().__init__()

    @check_permission()
    def get(self):
        query = Service.query

        if request.args.get('action') == 'next_ref_no':
            return {"ref_no": self._generate_reference_number()}, 200

        export_format = request.args.get('export')
        if export_format in ['excel', 'pdf']:
            return self.export_services(export_format)
        
        status = request.args.get('status', 'booked')
        start_date, end_date = self._parse_date_range()
        search_query = request.args.get('search_query', '')
        
        if start_date and end_date:
            end_date_plus = end_date + timedelta(days=1)
            query = query.filter(
                Service.date >= start_date,
                Service.date < end_date_plus
            )
        
        if status != 'all':
            query = query.filter_by(status=status)

        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.join(Customer, isouter=True)\
                         .join(Particular, isouter=True)\
                         .filter(db.or_(
                             db.func.lower(Service.ref_no).like(search_pattern),
                             db.func.lower(Customer.name).like(search_pattern),
                             db.func.lower(Particular.name).like(search_pattern)
                         ))
            
        services = query.all()
        return [self._format_service(s) for s in services], 200

    @check_permission()
    def post(self, action=None):
        action = (action or request.args.get('action', '')).lower().strip()
        return self.cancel_service() if action == 'cancel' else self.book_service()

    @check_permission()
    def patch(self):
        data = request.json
        if not (service_id := data.get('id')):
            abort(400, "Missing service ID")

        service = Service.query.get(service_id)
        if not service:
            abort(404, "Service not found")

        if service.status == 'cancelled':
            return self._update_cancelled_service(service, data)
        else:
            return self._update_active_service(service, data)

    @check_permission()
    def delete(self):
        if not (service_id := request.args.get('id')):
            abort(400, "Missing service ID")

        service = Service.query.get(service_id)
        if not service:
            abort(404, "Service not found")

        updated_by = getattr(g, 'username', 'system')
        service.updated_by = updated_by
        service.updated_at = datetime.now()
        db.session.add(service)

        try:
            if service.status == 'cancelled':
                # Step 1: Reverse the refund transaction
                if service.customer_refund_amount > 0:
                    if service.customer_refund_mode == 'wallet':
                        self._reverse_wallet_refund(service)
                    elif service.customer_refund_mode in ['cash', 'online']:
                        self._update_company_account(
                            service.customer_refund_mode,
                            service.customer_refund_amount,
                            'reversal',
                            f"Reversal of refund for service {service.id} deletion",
                            service.ref_no
                        )
                
                # Step 2: Reverse the original booking
                if service.customer_payment_mode == 'wallet':
                    self._reverse_wallet_payment(service)
                elif service.customer_payment_mode in ['cash', 'online']:
                    self._update_company_account(
                        service.customer_payment_mode,
                        -service.customer_charge,
                        'reversal',
                        f"Reversal of original booking for service {service.id} deletion",
                        service.ref_no
                    )

            else:
                self._reverse_wallet_payment(service)
                self._update_company_account(
                    service.customer_payment_mode,
                    -service.customer_charge,
                    'reversal',
                    f"Reversal of booking for service {service.id} deletion",
                    service.ref_no
                )

            # Step 3: Delete the service record
            db.session.delete(service)
            db.session.commit()
            return {"message": "Service deleted successfully with transaction reversal"}

        except Exception as e:
            db.session.rollback()
            abort(500, f"Deletion failed: {str(e)}")


    def _parse_date_range(self):
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return None, None
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        return start_date, end_date

    def _format_service(self, service):
        return {
            'id': service.id,
            'ref_no': service.ref_no,
            'customer_id': service.customer_id,
            'customer_name': Customer.query.get(service.customer_id).name,
            'particular_id': service.particular_id,
            'particular_name': Particular.query.get(service.particular_id).name if service.particular_id else None,
            'customer_charge': service.customer_charge,
            'status': service.status,
            'date': service.date.isoformat() if service.date else None,
            'customer_payment_mode': service.customer_payment_mode,
            'customer_refund_amount': service.customer_refund_amount,
            'customer_refund_mode': service.customer_refund_mode,
            'description': service.description,
            'created_at': service.created_at.isoformat(),
            'updated_at': service.updated_at.isoformat() if service.updated_at else None,
            'updated_by': service.updated_by
        }

    def _update_cancelled_service(self, service, data):
        new_refund = float(data.get('customer_refund_amount', service.customer_refund_amount))
        new_mode = data.get('customer_refund_mode', service.customer_refund_mode)

        if new_refund > service.customer_charge:
            abort(400, "Refund amount cannot exceed original charge")

        try:
            net_change = new_refund - service.customer_refund_amount
            
            if net_change != 0:
                self._adjust_customer_balance(
                    service.customer_id, 
                    net_change, 
                    new_mode,
                    f"Adjustment for Service {service.id} refund update",
                    service_ref=service.ref_no
                )
            
            service.customer_refund_amount = new_refund
            service.customer_refund_mode = new_mode
            service.updated_by = getattr(g, 'username', 'system')
            service.updated_at = datetime.now()
            
            db.session.commit()
            return {"message": "Cancelled service updated successfully"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Failed to update cancelled service: {str(e)}")

    def _update_active_service(self, service, data):
        updated_by = getattr(g, 'username', 'system')
        updates = {
            'particular_id': data.get('particular_id', service.particular_id),
            'description': data.get('description', service.description),
            'customer_charge': float(data.get('customer_charge', service.customer_charge)),
            'customer_payment_mode': data.get('customer_payment_mode', service.customer_payment_mode),
            'updated_by': updated_by,
            'updated_at': datetime.now()
        }
        
        if 'date' in data:
            updates['date'] = datetime.strptime(data['date'], '%Y-%m-%d').date()

        try:
            self._reverse_payment(service)
            
            for key, value in updates.items():
                setattr(service, key, value)
                
            self._process_payment(service)
            
            db.session.commit()
            return {"message": "Service updated successfully"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Update failed: {str(e)}")

    def _reverse_wallet_payment(self, service):
        """Reverse a service payment made via wallet/credit."""
        customer = Customer.query.get(service.customer_id)
        if not customer:
            return

        # Un-use credit first
        amount_to_restore = service.customer_charge
        
        # Un-use credit first
        credit_to_restore = min(amount_to_restore, customer.credit_used)
        customer.credit_used -= credit_to_restore
        remaining_to_restore = amount_to_restore - credit_to_restore
        
        # Credit the remaining amount to the wallet
        customer.wallet_balance += remaining_to_restore

    def _reverse_wallet_refund(self, service):
        """Reverse a refund that was credited to the customer's wallet/credit."""
        customer = Customer.query.get(service.customer_id)
        if not customer:
            return

        # The refund was a credit to the customer. To reverse it, we must debit them.
        # This means deducting from their wallet and then using their credit.
        amount_to_reverse = service.customer_refund_amount
        
        # First, deduct from the wallet
        wallet_deduction = min(amount_to_reverse, customer.wallet_balance)
        customer.wallet_balance -= wallet_deduction
        remaining_deduction = amount_to_reverse - wallet_deduction
        
        # Then, use credit for the remainder
        if remaining_deduction > 0:
            customer.credit_used += remaining_deduction


    def _reverse_payment(self, service):
        """Reverse the original payment transaction"""
        if service.customer_payment_mode in ['cash', 'online']:
            # Deduct original amount from company account
            self._update_company_account(
                service.customer_payment_mode,
                -service.customer_charge,
                'reversal',
                f"Reversal of original booking for service {service.id} deletion",
                service.ref_no
            )
        elif service.customer_payment_mode == 'wallet':
            customer = Customer.query.get(service.customer_id)
            if not customer:
                return
                
            # Calculate how much credit was used for this service
            credit_used_for_service = min(service.customer_charge, customer.credit_used)
            amount_to_restore_credit = min(service.customer_charge, credit_used_for_service)
            
            # Restore credit used
            customer.credit_used -= amount_to_restore_credit
            
            # Calculate remaining amount to credit to wallet
            remaining_credit = service.customer_charge - amount_to_restore_credit
            
            # Add remaining to wallet
            if remaining_credit > 0:
                customer.wallet_balance += remaining_credit


    def _adjust_customer_balance(self, customer_id, amount, mode, description, service_ref=None):
        if customer := Customer.query.get(customer_id):
            if mode == 'wallet':
                customer.wallet_balance += amount
            else:
                self._update_company_account(
                    mode,
                    -amount,
                    'adjustment',
                    description,
                    ref_no=service_ref
                )

    def _update_company_account(self, mode, amount, action, description, ref_no=None):
        if mode not in ['cash', 'online']:
            return
            
        last_balance = 0
        if last_entry := CompanyAccountBalance.query.filter_by(mode=mode)\
                            .order_by(CompanyAccountBalance.id.desc())\
                            .first():
            last_balance = last_entry.balance

        entry = CompanyAccountBalance(
            mode=mode,
            credited_amount=amount,
            credited_date=datetime.now(),
            balance=last_balance + amount,
            ref_no=ref_no,
            transaction_type='service',
            action=action,
            updated_by=getattr(g, 'username', 'system')
        )
        db.session.add(entry)

    def book_service(self):
        data = request.json
        required = ['customer_id', 'customer_charge', 'customer_payment_mode', 'date']
        if not all(field in data for field in required):
            abort(400, "Missing required fields")

        try:
            service = Service(
                customer_id=data['customer_id'],
                particular_id=data.get('particular_id'),
                description=data.get('description'),
                customer_charge=data['customer_charge'],
                customer_payment_mode=data['customer_payment_mode'],
                date=datetime.strptime(data['date'], '%Y-%m-%d').date(), 
                ref_no=self._generate_reference_number(),
                updated_by=getattr(g, 'username', 'system')
            )
            db.session.add(service)
            db.session.flush()

            self._process_payment(service)

            db.session.commit()
            return {"message": "Service booked", "id": service.id, "ref_no": service.ref_no}, 201
        except Exception as e:
            db.session.rollback()
            abort(500, f"Booking failed: {str(e)}")

    def _generate_reference_number(self):
        current_year = datetime.now().year
        max_ref = db.session.query(db.func.max(Service.ref_no)).filter(
            Service.ref_no.like(f"{current_year}/S/%")
        ).scalar()
        last_num = int(max_ref.split('/')[-1]) if max_ref and '/' in max_ref else 0
        return f"{current_year}/S/{last_num + 1:05d}"

    def cancel_service(self):
        data = request.json
        if not (service_id := data.get('service_id')):
            abort(400, "Missing service ID")

        service = Service.query.get(service_id)
        if not service:
            abort(404, "Service not found")
        if service.status == 'cancelled':
            abort(400, "Service already cancelled")

        refund_amt = float(data.get('customer_refund_amount', 0))
        refund_mode = data.get('customer_refund_mode', 'cash').lower().strip()

        # Validate refund amount
        if refund_amt > service.customer_charge:
            abort(400, "Refund amount cannot exceed original charge")

        try:
            # Process refund based on selected mode
            self._process_refund(service, refund_amt, refund_mode)

            # Update service record
            service.status = 'cancelled'
            service.updated_at = datetime.now()
            service.updated_by = getattr(g, 'username', 'system')
            service.customer_refund_amount = refund_amt
            service.customer_refund_mode = refund_mode
            
            db.session.commit()
            return {"message": "Service cancelled"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Cancellation failed: {str(e)}")

    def _process_payment(self, service):
        if service.customer_payment_mode in ['cash', 'online']:
            self._update_company_account(
                service.customer_payment_mode,
                service.customer_charge,
                'book',
                f"Service {service.id} booking",
                service.ref_no
            )
            
        if customer := Customer.query.get(service.customer_id):
            if service.customer_payment_mode == 'wallet':
                if customer.wallet_balance >= service.customer_charge:
                    customer.wallet_balance -= service.customer_charge
                else:
                    remaining = service.customer_charge - customer.wallet_balance
                    customer.wallet_balance = 0
                    if remaining <= (customer.credit_limit - customer.credit_used):
                        customer.credit_used += remaining
                    else:
                        raise Exception("Insufficient customer credit")

    def _process_refund(self, service, refund_amt, refund_mode):
        if refund_amt > 0 and (customer := Customer.query.get(service.customer_id)):
            if refund_mode == 'wallet':
                # First restore credit used for this service
                credit_used_for_service = min(service.customer_charge, customer.credit_used)
                amount_to_restore_credit = min(refund_amt, credit_used_for_service)
                
                # Reduce credit used
                customer.credit_used -= amount_to_restore_credit
                
                # Calculate remaining amount to credit to wallet
                remaining_refund = refund_amt - amount_to_restore_credit
                
                # Add remaining to wallet
                if remaining_refund > 0:
                    customer.wallet_balance += remaining_refund
            else:
                # For cash/online refunds, deduct from company account
                self._update_company_account(
                    refund_mode,
                    -refund_amt,
                    'refund',
                    f"Refund for Service {service.id}",
                    service.ref_no
                )

    def export_services(self, format_type):
        status = request.args.get('status', 'booked')
        start_date, end_date = self._parse_date_range()
        search_query = request.args.get('search_query', '')
        
        query = Service.query
        
        if start_date and end_date:
            end_date_plus = end_date + timedelta(days=1)
            query = query.filter(
                Service.date >= start_date,
                Service.date < end_date_plus
            )
        
        if status != 'all':
            query = query.filter_by(status=status)

        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.join(Customer, isouter=True)\
                         .join(Particular, isouter=True)\
                         .filter(db.or_(
                             db.func.lower(Service.ref_no).like(search_pattern),
                             db.func.lower(Customer.name).like(search_pattern),
                             db.func.lower(Particular.name).like(search_pattern)
                         ))

        services = query.all()
        data = [self._format_service_for_export(s) for s in services]

        if format_type == 'excel':
            return self.export_excel(data, status)
        elif format_type == 'pdf':
            return self.export_pdf(data, status)
        else:
            abort(400, "Invalid export format")

    def _format_service_for_export(self, service):
        data = {
            'Reference No': service.ref_no,
            'Date': service.date.strftime('%Y-%m-%d') if service.date else '',
            'Customer': Customer.query.get(service.customer_id).name,
            'Particular': Particular.query.get(service.particular_id).name if service.particular_id else None,
            'Customer Charge': service.customer_charge,
            'Status': service.status.capitalize(),
            'Payment Mode': service.customer_payment_mode.capitalize(),
            'Description': service.description,
        }
        
        if service.status == 'cancelled':
            data.update({
                'Refund Amount': service.customer_refund_amount,
                'Refund Mode': service.customer_refund_mode.capitalize(),
            })
        
        return data

    def export_excel(self, data, status):
        return generate_export_excel(data=data, status=status)

    def export_pdf(self, data, status):
        total_charge_key = 'Customer Charge'
        total_refund_key = 'Refund Amount'
        total_charge = sum(row.get(total_charge_key, 0) for row in data)
        total_refund = sum(row.get(total_refund_key, 0) for row in data) if status == 'cancelled' else 0
        
        summary_totals = {
            "Total Services": len(data),
            "Total Customer Charge": total_charge
        }
        if status == 'cancelled':
            summary_totals["Total Refund Amount"] = total_refund
            
        return generate_export_pdf(
            data=data,
            title=f"Service Export Report ({status.capitalize()} Services)",
            date_range_start=request.args.get('start_date', ''),
            date_range_end=request.args.get('end_date', ''),
            summary_totals=summary_totals,
            status=status
        )