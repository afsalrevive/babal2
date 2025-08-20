# applications/common_booking_resource.py

from flask import request, abort, g
from applications.model import db, Customer, Agent, CompanyAccountBalance
from datetime import datetime, timedelta
from applications.pdf_excel_export_helpers import generate_export_pdf, generate_export_excel

class CommonBookingResource:
    def __init__(self, model, ref_prefix):
        self.MODEL = model
        self.REF_PREFIX = ref_prefix
    
    # The get_records method has been removed from this class as per the new ticket_api/visa_api implementations.
    
    def book_record(self):
        raise NotImplementedError
        
    def cancel_record(self):
        raise NotImplementedError

    def update_record(self, model, record_id, ref_type):
        obj = model.query.get(record_id)
        if not obj:
            abort(404, f"{ref_type.capitalize()} not found")

        data = request.json
        if obj.status == 'cancelled':
            return self._update_cancelled_record(obj, data, ref_type)
        else:
            return self._update_active_record(obj, data, ref_type)

    def delete_record(self, model, record_id, ref_type):
        obj = model.query.get(record_id)
        if not obj:
            abort(404, f"{ref_type.capitalize()} not found")

        updated_by = getattr(g, 'username', 'system')
        obj.updated_by = updated_by
        obj.updated_at = datetime.now()
        db.session.add(obj)

        try:
            if obj.status == 'cancelled':
                return self._delete_cancelled_record(obj, ref_type)
            else:
                return self._delete_active_record(obj, ref_type)
        except Exception as e:
            db.session.rollback()
            abort(500, f"Deletion failed: {str(e)}")

    def cancel_common_record(self, model, record_id, ref_type):
        record = model.query.get(record_id)
        if not record:
            abort(404, f"{ref_type.capitalize()} not found")
        if record.status == 'cancelled':
            abort(400, f"{ref_type.capitalize()} already cancelled")

        data = request.json
        refund_amt = float(data.get('customer_refund_amount', 0))
        refund_mode = data.get('customer_refund_mode', 'cash').lower().strip()
        recovery_amt = float(data.get('agent_recovery_amount', 0))
        recovery_mode = data.get('agent_recovery_mode', 'cash').lower().strip()

        try:
            self._process_refunds(record, refund_amt, refund_mode, recovery_amt, recovery_mode)

            record.status = 'cancelled'
            record.updated_at = datetime.now()
            record.updated_by = getattr(g, 'username', 'system')
            
            net_amount = 0
            if record.customer_refund_mode in ['cash', 'online']:
                net_amount -= record.customer_refund_amount
            if record.agent_id and record.agent_recovery_mode in ['cash', 'online']:
                net_amount += record.agent_recovery_amount
            
            if net_amount != 0:
                mode = self._get_account_mode(record)
                if mode:
                    self._update_company_account(mode, net_amount, 'cancel', f"{ref_type.capitalize()} {record.id} cancel",
                                                 ref_no=record.ref_no, transaction_type=ref_type)

            db.session.commit()
            return {"message": f"{ref_type.capitalize()} cancelled"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Cancellation failed: {str(e)}")

    def _update_active_record(self, record, data, ref_type):
        updated_by = getattr(g, 'username', 'system')
        updates = {
            'travel_location_id': data.get('travel_location_id', record.travel_location_id),
            'customer_id': data.get('customer_id', record.customer_id),
            'agent_id': data.get('agent_id', record.agent_id),
            'ticket_type_id': data.get('ticket_type_id', record.ticket_type_id) if hasattr(record, 'ticket_type_id') else None,
            'visa_type_id': data.get('visa_type_id', record.visa_type_id) if hasattr(record, 'visa_type_id') else None,
            'passenger_id': data.get('passenger_id', record.passenger_id),
            'particular_id': data.get('particular_id', record.particular_id),
            'description': data.get('description', record.description),
            'customer_charge': float(data.get('customer_charge', record.customer_charge)),
            'agent_paid': float(data.get('agent_paid', record.agent_paid)),
            'customer_payment_mode': data.get('customer_payment_mode', record.customer_payment_mode),
            'agent_payment_mode': data.get('agent_payment_mode', record.agent_payment_mode),
            'date': datetime.strptime(data.get('date'), '%Y-%m-%d') if data.get('date') else record.date,
            'updated_by': updated_by,
            'updated_at': datetime.now()
        }
        if hasattr(record,'ticker_type_id'):
            updates['ticket_type_id'] = data.get('ticket_type_id', getattr(record, 'ticket_type_id'))
        if hasattr(record, 'visa_type_id'):
            updates['visa_type_id'] = data.get('visa_type_id', getattr(record, 'visa_type_id'))
        
        updates['profit'] = updates['customer_charge'] - updates['agent_paid']

        try:
            self._reverse_payments(record, ref_type)

            for key, value in updates.items():
                setattr(record, key, value)
            
            self._process_payments(record, 'update', ref_type)

            db.session.commit()
            return {"message": f"{ref_type.capitalize()} updated successfully"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Update failed: {str(e)}")

    def _update_cancelled_record(self, record, data, ref_type):
        new_customer_refund = float(data.get('customer_refund_amount', record.customer_refund_amount))
        new_customer_mode = data.get('customer_refund_mode', record.customer_refund_mode)
        new_agent_recovery = float(data.get('agent_recovery_amount', record.agent_recovery_amount))
        new_agent_mode = data.get('agent_recovery_mode', record.agent_recovery_mode)

        if new_customer_refund > record.customer_charge:
            abort(400, "Refund amount cannot exceed original charge")
        if record.agent_id and new_agent_recovery > record.agent_paid:
            abort(400, "Recovery amount cannot exceed original agent payment")

        try:
            customer_net_change = new_customer_refund - record.customer_refund_amount
            agent_net_change = new_agent_recovery - record.agent_recovery_amount
            
            if customer_net_change != 0:
                self._adjust_customer_balance(
                    record.customer_id, 
                    -customer_net_change, 
                    new_customer_mode,
                    f"Adjustment for {ref_type.capitalize()} {record.id} refund update",
                    ref_no=record.ref_no,
                    transaction_type=ref_type
                )
            
            if agent_net_change != 0 and record.agent_id:
                self._adjust_agent_balance(
                    record.agent_id, 
                    -agent_net_change,
                    new_agent_mode,
                    f"Adjustment for {ref_type.capitalize()} {record.id} recovery update",
                    ref_no=record.ref_no,
                    transaction_type=ref_type
                )
            
            record.customer_refund_amount = new_customer_refund
            record.customer_refund_mode = new_customer_mode
            record.agent_recovery_amount = new_agent_recovery
            record.agent_recovery_mode = new_agent_mode
            record.updated_by = getattr(g, 'username', 'system')
            record.updated_at = datetime.now()
            
            db.session.commit()
            return {"message": "Cancelled record updated successfully"}
        except Exception as e:
            db.session.rollback()
            abort(500, f"Failed to update cancelled record: {str(e)}")
            
    def _delete_cancelled_record(self, record, ref_type):
        customer_net_effect = record.customer_charge - record.customer_refund_amount
        agent_net_effect = record.agent_paid - record.agent_recovery_amount
        
        self._reverse_net_effect(record, customer_net_effect, agent_net_effect, ref_type)
        
        db.session.delete(record)
        db.session.commit()
        return {"message": "Cancelled record deleted with full transaction reversal"}

    def _delete_active_record(self, record, ref_type):
        self._reverse_payments(record, ref_type)
        db.session.delete(record)
        db.session.commit()
        return {"message": "Record deleted successfully"}
        
    def _parse_date_range(self):
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        return start_date, end_date

    def _adjust_customer_balance(self, customer_id, amount, mode, description, ref_no=None, transaction_type='generic'):
        if customer := Customer.query.get(customer_id):
            if mode == 'wallet':
                customer.wallet_balance += amount
            elif mode in ['cash', 'online']:
                self._update_company_account(mode, -amount, 'adjustment', description, ref_no=ref_no, transaction_type=transaction_type)

    def _adjust_agent_balance(self, agent_id, amount, mode, description, ref_no=None, transaction_type='generic'):
        if agent := Agent.query.get(agent_id):
            if mode == 'wallet':
                agent.wallet_balance += amount
            elif mode in ['cash', 'online']:
                self._update_company_account(mode, amount, 'adjustment', description, ref_no=ref_no, transaction_type=transaction_type)

    def _update_company_account(self, mode, amount, action, description, ref_no=None, transaction_type='generic'):
        if mode not in ['cash', 'online']:
            return

        last_balance = 0
        if last_entry := CompanyAccountBalance.query.filter_by(mode=mode).order_by(CompanyAccountBalance.id.desc()).first():
            last_balance = last_entry.balance

        new_balance = round(last_balance + amount, 2)
        entry = CompanyAccountBalance(
            mode=mode,
            credited_amount=amount,
            credited_date=datetime.now(),
            balance=new_balance,
            ref_no=ref_no,
            transaction_type=transaction_type,
            action=action,
            updated_by=getattr(g, 'username', 'system')
        )
        db.session.add(entry)
    
    def _reverse_net_effect(self, obj, customer_net_effect, agent_net_effect, ref_type):
        if customer_net_effect:
            self._adjust_customer_balance(obj.customer_id, customer_net_effect, obj.customer_refund_mode,
                                          f"Reversal for {ref_type.capitalize()} {obj.id} deletion", ref_no=obj.ref_no, transaction_type=ref_type)
        if agent_net_effect and obj.agent_id:
            self._adjust_agent_balance(obj.agent_id, agent_net_effect, obj.agent_recovery_mode,
                                       f"Reversal for {ref_type.capitalize()} {obj.id} deletion", ref_no=obj.ref_no, transaction_type=ref_type)

    def _update_financials(self, obj, action, ref_type):
        net_amount = 0
        if action in ['book', 'update']:
            if obj.customer_payment_mode in ['cash', 'online']:
                net_amount += obj.customer_charge
            if obj.agent_id and obj.agent_payment_mode in ['cash', 'online']:
                net_amount -= obj.agent_paid
        elif action == 'cancel':
            if obj.customer_refund_mode in ['cash', 'online']:
                net_amount -= obj.customer_refund_amount
            if obj.agent_id and obj.agent_recovery_mode in ['cash', 'online']:
                net_amount += obj.agent_recovery_amount
        
        if net_amount:
            mode = self._get_account_mode(obj)
            if mode:
                self._update_company_account(mode, net_amount, action, f"{ref_type.capitalize()} {obj.id} {action}",
                                             ref_no=obj.ref_no, transaction_type=ref_type)

    def _get_account_mode(self, obj):
        modes = [
            getattr(obj, 'customer_payment_mode', None),
            getattr(obj, 'agent_payment_mode', None) if getattr(obj, 'agent_id', None) else None,
            getattr(obj, 'customer_refund_mode', None),
            getattr(obj, 'agent_recovery_mode', None) if getattr(obj, 'agent_id', None) else None
        ]
        for field in modes:
            if field in ['cash', 'online']:
                return field
        return None
    
    def _process_payments(self, obj, action, ref_type):
        if customer := Customer.query.get(obj.customer_id):
            self._process_entity_payment(
                entity=customer,
                amount=obj.customer_charge,
                mode=obj.customer_payment_mode,
                is_customer=True
            )
        
        if obj.agent_id and obj.agent_paid > 0:
            if agent := Agent.query.get(obj.agent_id):
                self._process_entity_payment(
                    entity=agent,
                    amount=obj.agent_paid,
                    mode=obj.agent_payment_mode,
                    is_customer=False
                )
        
        self._update_financials(obj, action, ref_type)
    
    def _process_entity_payment(self, entity, amount, mode, is_customer):
        mode = mode.lower().strip()
        
        if mode == 'wallet':
            self._process_wallet_payment(entity, amount, is_customer)
        elif mode in ['cash', 'online']:
            pass
        else:
            raise Exception(f"Invalid payment mode: {mode}")
    
    def _process_wallet_payment(self, entity, amount, is_customer):
        if is_customer:
            if entity.wallet_balance >= amount:
                entity.wallet_balance -= amount
            else:
                remaining = amount - entity.wallet_balance
                entity.wallet_balance = 0
                if remaining <= (entity.credit_limit - entity.credit_used):
                    entity.credit_used += remaining
                else:
                    raise Exception("Insufficient customer credit")
        else:
            if entity.wallet_balance >= amount:
                entity.wallet_balance -= amount
            else:
                remaining = amount - entity.wallet_balance
                entity.wallet_balance = 0
                if remaining <= entity.credit_balance:
                    entity.credit_balance -= remaining
                else:
                    raise Exception("Insufficient agent credit")

    def _reverse_payments(self, obj, ref_type):
        self._reverse_customer_payment(obj, ref_type)
        self._reverse_agent_payment(obj, ref_type)

    def _reverse_customer_payment(self, obj, ref_type):
        if not (customer := Customer.query.get(obj.customer_id)):
            return
        
        mode = (obj.customer_payment_mode or '').lower().strip()
        amount = obj.customer_charge
        
        if mode == 'wallet':
            refund_to_credit = min(amount, customer.credit_used)
            customer.credit_used -= refund_to_credit
            refund_to_wallet = amount - refund_to_credit
            customer.wallet_balance += refund_to_wallet
        elif mode in ['cash', 'online']:
            self._update_company_account(mode, -amount, 'reversal', f"Reversal for {ref_type.capitalize()} {obj.id}",
                                         ref_no=obj.ref_no, transaction_type=ref_type)

    def _reverse_agent_payment(self, obj, ref_type):
        if not (obj.agent_paid > 0 and obj.agent_id):
            return
            
        if not (agent := Agent.query.get(obj.agent_id)):
            return

        mode = (obj.agent_payment_mode or '').lower().strip()
        amount = obj.agent_paid
        
        if mode == 'wallet':
            credit_deficit = agent.credit_limit - agent.credit_balance
            refund_to_credit = min(amount, credit_deficit)
            agent.credit_balance += refund_to_credit
            refund_to_wallet = amount - refund_to_credit
            agent.wallet_balance += refund_to_wallet
        elif mode in ['cash', 'online']:
            self._update_company_account(mode, amount, 'reversal', f"Reversal for {ref_type.capitalize()} {obj.id}",
                                         ref_no=obj.ref_no, transaction_type=ref_type)

    def _process_refunds(self, obj, refund_amt, refund_mode, recovery_amt, recovery_mode):
        if refund_amt > 0:
            if customer := Customer.query.get(obj.customer_id):
                if refund_mode == 'wallet':
                    refund_to_credit = min(refund_amt, customer.credit_used)
                    customer.credit_used -= refund_to_credit
                    refund_to_wallet = refund_amt - refund_to_credit
                    customer.wallet_balance += refund_to_wallet
                
                obj.customer_refund_amount = refund_amt
                obj.customer_refund_mode = refund_mode

        if recovery_amt > 0 and obj.agent_id:
            if agent := Agent.query.get(obj.agent_id):
                if recovery_mode == 'wallet':
                    credit_deficit = agent.credit_limit - agent.credit_balance
                    refund_to_credit = min(recovery_amt, credit_deficit)
                    agent.credit_balance += refund_to_credit
                    refund_to_wallet = recovery_amt - refund_to_credit
                    agent.wallet_balance += refund_to_wallet
                
                obj.agent_recovery_amount = recovery_amt
                obj.agent_recovery_mode = recovery_mode
    
    def export_excel_pdf(self, model, ref_type):
        export_format = request.args.get('export')
        status = request.args.get('status', 'booked')
        start_date, end_date = self._parse_date_range()
        search_query = request.args.get('search_query', '')
        end_date_plus = end_date + timedelta(days=1)

        query = model.query.filter(
            model.date >= start_date,
            model.date < end_date_plus
        )

        if status != 'all':
            query = query.filter_by(status=status)

        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.join(Customer, isouter=True)\
                         .join(Agent, isouter=True)\
                         .filter(db.or_(
                             db.func.lower(model.ref_no).like(search_pattern),
                             db.func.lower(Customer.name).like(search_pattern),
                             db.func.lower(Agent.name).like(search_pattern)
                         ))

        records = query.all()
        format_func = getattr(self, f"_format_for_export", None)
        if format_func:
            data = [format_func(r) for r in records]
        else:
            return abort(500, "Formatter not implemented")

        if export_format == 'excel':
            # CHANGE IS HERE
            return generate_export_excel(data=data, status=status, transaction_type=ref_type)
        elif export_format == 'pdf':
            return generate_export_pdf(
                data=data,
                title=f"{ref_type.capitalize()} Export Report ({status.capitalize()} {ref_type.capitalize()}s)",
                date_range_start=request.args.get('start_date', ''),
                date_range_end=request.args.get('end_date', ''),
                summary_totals=self.get_summary_totals(data, status),
                exclude_columns=['Created At', 'Updated At', 'Updated By'],
                status=status
            )
        else:
            abort(400, "Invalid export format")

            
    def get_summary_totals(self, data, status):
        money_cols = ['Customer Charge', 'Agent Paid', 'Profit']
        if status == 'cancelled':
            money_cols.extend(['Customer Refund Amount', 'Agent Recovery Amount'])
        
        totals = {col: sum(float(row.get(col, 0) or 0) for row in data) for col in money_cols}
        
        return {
            f"Total {self.MODEL.__name__}s": len(data),
            **{f"Total {col}": total for col, total in totals.items()}
        }