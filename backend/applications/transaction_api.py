# applications/transaction_api.py
from flask import request,g
from flask_restful import Resource
from applications.utils import check_permission
from applications.model import db, Customer, Agent, Partner, Transaction ,Passenger, CompanyAccountBalance, Particular
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from applications.pdf_excel_export_helpers import generate_export_pdf, generate_export_excel

TRANSACTION_TYPES = ['payment', 'receipt', 'refund', 'wallet_transfer']

MODEL_MAP = {
    'customer': Customer,
    'agent': Agent,
    'partner': Partner,
    'passenger': Passenger
}

REF_NO_PREFIXES = {
    'payment': 'P',
    'receipt': 'R',
    'refund': 'E',
    'wallet_transfer': 'WT'
}

def get_entity(entity_type, entity_id):
    if entity_id is None or entity_type == 'others':
        return None
    model = MODEL_MAP.get(entity_type)
    return model.query.get(entity_id) if model else None

def adjust_company_balance(mode, amount, direction='out', ref_no=None, transaction_type=None, action='add', updated_by='system'):
    """
    Updates the company account balance for a given mode.
    The new balance is rounded to 2 decimal places to prevent floating-point inaccuracies.
    """
    if not mode:
        return
        # raise ValueError("Missing mode for company balance adjustment.")

    if mode not in ['cash', 'online']:
        return

    last = CompanyAccountBalance.query.filter_by(mode=mode).order_by(CompanyAccountBalance.id.desc()).first()
    prev = last.balance if last else 0.0
    delta = amount if direction == 'in' else -amount
    # Round the new balance to 2 decimal places
    new_balance = round(prev + delta, 2)

    db.session.add(CompanyAccountBalance(
        mode=mode,
        credited_amount=delta,
        balance=new_balance,
        ref_no=ref_no,
        transaction_type=transaction_type,
        action=action,
        updated_by=updated_by
    ))


def get_entity_name(entity_type, entity_id):
    if entity_id is None:
        return None
    entity = get_entity(entity_type, entity_id)
    return entity.name if entity else None

def get_particular_name(particular_id):
    if not particular_id:
        return None
    p = Particular.query.get(particular_id)
    return p.name if p else None


def get_transaction_payload(t: Transaction):
    payload = {
        "id": t.id,
        "ref_no": t.ref_no,
        "entity_type": t.entity_type,
        "entity_id": t.entity_id,
        "entity_name": get_entity_name(t.entity_type, t.entity_id),
        "transaction_type": t.transaction_type,
        "pay_type": t.pay_type,
        "mode": t.mode,
        "amount": t.amount,
        "date": t.date.isoformat() if t.date else None,
        "timestamp": t.date.timestamp() * 1000 if t.date else None,
        "description": t.description,
        "particular_id": t.particular_id,
        "particular_name": get_particular_name(t.particular_id),
        "ticket_id": getattr(t, 'ticket_id', None)
    }
    
    if t.extra_data:
        payload.update({
            k: v for k, v in t.extra_data.items()
            if v is not None
        })
        
        if t.transaction_type == 'refund' and 'refund_direction' in t.extra_data:
            payload['refund_direction'] = t.extra_data['refund_direction'].lower()
        if 'from_entity_name' in t.extra_data:
            payload['from_entity_name'] = t.extra_data['from_entity_name']
        if 'to_entity_name' in t.extra_data:
            payload['to_entity_name'] = t.extra_data['to_entity_name']
    
    return payload

def generate_ref_no(transaction_type):
    """Generate unique reference number for transaction"""
    year = datetime.now().year
    prefix = REF_NO_PREFIXES.get(transaction_type, 'T')
    
    last_trans = Transaction.query.filter(
        Transaction.ref_no.like(f"{year}/{prefix}/%")
    ).order_by(Transaction.ref_no.desc()).first()
    
    if last_trans:
        try:
            last_seq = int(last_trans.ref_no.split('/')[-1])
        except (ValueError, IndexError):
            last_seq = 0
        seq = last_seq + 1
    else:
        seq = 1

    return f"{year}/{prefix}/{seq:05d}"
def apply_credit_wallet_logic(entity, amount, entity_type, mode='deduct'):
    """Apply wallet/credit logic based on entity type"""
    if entity_type == 'customer':
        if mode == 'deduct':
            wallet = entity.wallet_balance
            credit_available = entity.credit_limit - entity.credit_used
            if wallet + credit_available < amount:
                raise ValueError("Insufficient funds")
            deduct_wallet = min(wallet, amount)
            entity.wallet_balance -= deduct_wallet
            entity.credit_used += (amount - deduct_wallet)
        elif mode == 'revert':
            repay_credit = min(entity.credit_used, amount)
            entity.credit_used -= repay_credit
            entity.wallet_balance += (amount - repay_credit)
            
    elif entity_type == 'agent':
        if mode == 'deduct':
            if entity.wallet_balance + entity.credit_balance < amount:
                raise ValueError("Insufficient funds")
            deduct_wallet = min(entity.wallet_balance, amount)
            entity.wallet_balance -= deduct_wallet
            entity.credit_balance -= (amount - deduct_wallet)
        elif mode == 'revert':
            credit_deficit = entity.credit_limit - entity.credit_balance
            repay_credit = min(credit_deficit, amount)
            entity.credit_balance += repay_credit
            entity.wallet_balance += (amount - repay_credit)
            
    elif entity_type == 'partner':
        if mode == 'deduct':
            if not entity.allow_negative_wallet and entity.wallet_balance < amount:
                raise ValueError("Insufficient wallet balance")
            entity.wallet_balance -= amount
        elif mode == 'revert':
            entity.wallet_balance += amount

def apply_company_adjustment(transaction, direction):
    adjust_company_balance(transaction.mode, transaction.amount, direction)

def parse_transaction_date(raw_date):
    if isinstance(raw_date, (int, float)):
        return datetime.fromtimestamp(raw_date / 1000)
    elif isinstance(raw_date, str):
        return parse_date(raw_date)
    return datetime.now()

def process_wallet_transfer(transaction):
    """Apply wallet-to-wallet transfer between entities with credit and wallet logic"""
    extra = transaction.extra_data or {}
    from_type = extra.get('from_entity_type')
    to_type = extra.get('to_entity_type')
    from_id = extra.get('from_entity_id')
    to_id = extra.get('to_entity_id')
    amount = transaction.amount

    from_entity = get_entity(from_type, from_id)
    to_entity = get_entity(to_type, to_id)

    if not from_entity or not to_entity:
        raise ValueError("Both source and destination entities must exist")

    apply_credit_wallet_logic(from_entity, amount, from_type, mode='deduct')
    if hasattr(from_entity, '_deduct_breakdown'):
        transaction.extra_data.update({
            "from_wallet_deducted": from_entity._deduct_breakdown.get("wallet_deducted", 0),
            "from_credit_used": from_entity._deduct_breakdown.get("credit_used", 0)
        })

    apply_credit_wallet_logic(to_entity, amount, to_type, mode='revert')
    if hasattr(to_entity, '_revert_breakdown'):
        transaction.extra_data.update({
            "to_credit_repaid": to_entity._revert_breakdown.get("credit_repaid", 0),
            "to_wallet_added": to_entity._revert_breakdown.get("wallet_added", 0)
        })

    transaction.extra_data.update({
        "from_entity_name": from_entity.name,
        "to_entity_name": to_entity.name
    })

    db.session.add(from_entity)
    db.session.add(to_entity)

def update_wallet_and_company(transaction):
    etype = transaction.entity_type
    ttype = transaction.transaction_type
    pay_type = transaction.pay_type
    amount = transaction.amount
    extra = transaction.extra_data or {}
    ref_no = transaction.ref_no
    updated_by = transaction.updated_by or 'system'

    def log_company(mode, direction='out', action='add'):
        if mode not in ['cash', 'online']:
            return
        adjust_company_balance(
            mode=mode,
            amount=amount,
            direction=direction,
            ref_no=ref_no,
            transaction_type=ttype,
            action=action,
            updated_by=updated_by
        )
        transaction.extra_data["company_adjusted"] = True

    if ttype == 'payment':
        entity = get_entity(etype, transaction.entity_id)
        if etype == 'agent':
            if pay_type == 'cash_deposit':
                apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='revert')
                transaction.extra_data["credited_entity"] = True
            elif pay_type == 'other_expense' and extra.get('deduct_from_account'):
                apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='deduct')
                transaction.extra_data["debited_entity"] = True
            log_company(transaction.mode, direction='out')

        elif etype in ['customer', 'partner']:
            if pay_type == 'cash_withdrawal':
                apply_credit_wallet_logic(entity, amount, entity_type=etype, mode='deduct')
                transaction.extra_data["debited_entity"] = True
            elif pay_type == 'other_expense' and extra.get('deduct_from_account'):
                apply_credit_wallet_logic(entity, amount, entity_type=etype, mode='deduct')
                transaction.extra_data["debited_entity"] = True
            log_company(transaction.mode, direction='out')

        if entity:
            db.session.add(entity)

    elif ttype == 'receipt':
        entity = get_entity(etype, transaction.entity_id)
        if etype == 'customer':
            if pay_type == 'cash_deposit' or (pay_type == 'other_receipt' and extra.get('credit_to_account')):
                apply_credit_wallet_logic(entity, amount, entity_type='customer', mode='revert')
                transaction.extra_data["credited_entity"] = True
            log_company(transaction.mode, direction='in')
            
        elif etype == 'partner':
            if pay_type == 'cash_deposit' or (pay_type == 'other_receipt' and extra.get('credit_to_account')):
                entity.wallet_balance += amount
                transaction.extra_data["credited_entity"] = True
            log_company(transaction.mode, direction='in')
            
        elif etype == 'agent':
            if pay_type == 'other_receipt' and extra.get('credit_to_account'):
                apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='deduct')
                transaction.extra_data["debited_entity"] = True
            log_company(transaction.mode, direction='in')
            
        elif etype == 'others':
            log_company(transaction.mode, direction='in')

        if entity:
            db.session.add(entity)

    elif ttype == 'refund':
        direction = extra.get('refund_direction')
        f_type = extra.get('from_entity_type')
        f_id = extra.get('from_entity_id')
        f_mode = extra.get('mode_for_from')
        t_type = extra.get('to_entity_type')
        t_id = extra.get('to_entity_id')
        t_mode = extra.get('mode_for_to')
        credit_to_account = extra.get('credit_to_account')
        deduct_from_account = extra.get('deduct_from_account')

        if direction == 'incoming':
            entity = get_entity(f_type, f_id) if f_type != 'others' else None
            
            if f_type == 'others' or f_mode in ['cash', 'online']:
                log_company(t_mode, direction='in')
                
                if f_type != 'others' and credit_to_account:
                    if f_type in ['customer', 'partner']:
                        apply_credit_wallet_logic(entity, amount, entity_type=f_type, mode='revert')
                        transaction.extra_data["credited_entity"] = True
                    elif f_type == 'agent':
                        apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='revert')
                        transaction.extra_data["credited_entity"] = True
            
            elif f_mode == 'wallet':
                if f_type in ['customer', 'partner']:
                    apply_credit_wallet_logic(entity, amount, entity_type=f_type, mode='deduct')
                    transaction.extra_data["debited_entity"] = True
                elif f_type == 'agent':
                    apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='deduct')
                    transaction.extra_data["debited_entity"] = True

            if entity:
                db.session.add(entity)

        elif direction == 'outgoing':
            entity = get_entity(t_type, t_id) if t_type != 'others' else None
            
            if f_mode != 'service_availed':
                log_company(f_mode, direction='out')
            
            if t_type in ['customer', 'partner']:
                if deduct_from_account:
                    apply_credit_wallet_logic(entity, amount, entity_type=t_type, mode='deduct')
                    transaction.extra_data["debited_entity"] = True
                elif credit_to_account:
                    apply_credit_wallet_logic(entity, amount, entity_type=t_type, mode='revert')
                    transaction.extra_data["credited_entity"] = True
            
            elif t_type == 'agent' and credit_to_account:
                apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='revert')
                transaction.extra_data["credited_entity"] = True
            
            if entity:
                db.session.add(entity)


def revert_wallet_and_company(transaction):
    ttype = transaction.transaction_type
    amount = transaction.amount
    mode = transaction.mode
    etype = transaction.entity_type
    extra = transaction.extra_data or {}
    ref_no = transaction.ref_no
    updated_by = transaction.updated_by or 'system'

    def log_company(mode, direction):
        if not mode:
            return
        reverse_direction = 'in' if direction == 'out' else 'out'
        adjust_company_balance(
            mode=mode,
            amount=amount,
            direction=reverse_direction,
            ref_no=ref_no,
            transaction_type=ttype,
            action='delete',
            updated_by=updated_by
        )

    if ttype in ['payment', 'receipt']:
        entity = get_entity(etype, transaction.entity_id)
        if entity:
            if extra.get("debited_entity"):
                if etype == 'customer':
                    apply_credit_wallet_logic(entity, amount, entity_type='customer', mode='revert')
                elif etype == 'agent':
                    apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='revert')
                elif etype == 'partner':
                    apply_credit_wallet_logic(entity, amount, entity_type='partner', mode='revert')
            
            if extra.get("credited_entity"):
                if etype == 'customer':
                    apply_credit_wallet_logic(entity, amount, entity_type='customer', mode='deduct')
                elif etype == 'agent':
                    apply_credit_wallet_logic(entity, amount, entity_type='agent', mode='deduct')
                elif etype == 'partner':
                    apply_credit_wallet_logic(entity, amount, entity_type='partner', mode='deduct')
            
            db.session.add(entity)
        
        # Check the company_adjusted flag to prevent duplicate entries
        if extra.get("company_adjusted"):
            direction = 'out' if ttype == 'payment' else 'in'
            log_company(mode, direction)

    elif ttype == 'wallet_transfer':
        from_entity = get_entity(extra.get('from_entity_type'), extra.get('from_entity_id'))
        to_entity = get_entity(extra.get('to_entity_type'), extra.get('to_entity_id'))
        
        if to_entity:
            apply_credit_wallet_logic(to_entity, amount, extra.get('to_entity_type'), mode='deduct')
            db.session.add(to_entity)
        if from_entity:
            apply_credit_wallet_logic(from_entity, amount, extra.get('from_entity_type'), mode='revert')
            db.session.add(from_entity)
        return
    
    elif ttype == 'refund':
        direction = extra.get('refund_direction')
        f_type = extra.get('from_entity_type')
        f_id = extra.get('from_entity_id')
        t_type = extra.get('to_entity_type')
        t_id = extra.get('to_entity_id')
        f_mode = extra.get('mode_for_from')
        t_mode = extra.get('mode_for_to')
        company_adjusted = extra.get("company_adjusted")

        if direction == 'incoming':
            entity = get_entity(f_type, f_id)
            if entity:
                if extra.get("debited_entity"):
                    apply_credit_wallet_logic(entity, amount, f_type, mode='revert')
                    db.session.add(entity)
                if extra.get("credited_entity"):
                    apply_credit_wallet_logic(entity, amount, f_type, mode='deduct')
                    db.session.add(entity)
            if company_adjusted:
                log_company(t_mode, direction='in')

        elif direction == 'outgoing':
            entity = get_entity(t_type, t_id)
            if entity:
                if extra.get("debited_entity"):
                    apply_credit_wallet_logic(entity, amount, t_type, mode='revert')
                    db.session.add(entity)
                if extra.get("credited_entity"):
                    apply_credit_wallet_logic(entity, amount, t_type, mode='deduct')
                    db.session.add(entity)
            if company_adjusted:
                log_company(f_mode, direction='out')


class TransactionResource(Resource):
    @check_permission()
    def get(self, transaction_type):
        if transaction_type not in TRANSACTION_TYPES:
            return {'error': 'Invalid transaction type'}, 400
        
        if request.args.get('mode') == 'form':
            return {'ref_no': generate_ref_no(transaction_type)}, 200
        
        export_format = request.args.get('export')
        if export_format in ['excel', 'pdf']:
            return self._export_transactions(transaction_type, export_format)
        
        # New logic to return all records for client-side pagination
        query = Transaction.query.filter_by(transaction_type=transaction_type).order_by(Transaction.date.desc())
        transactions = query.all()

        return {"transactions": [get_transaction_payload(t) for t in transactions]}, 200

    @check_permission()
    def post(self, transaction_type):
        if transaction_type not in TRANSACTION_TYPES:
            return {'error': 'Invalid transaction type'}, 400
        
        data = request.json
        
        try:
            amount = data.get('amount')
            if not amount or float(amount) <= 0:
                return {'error': 'Amount must be greater than 0'}, 400
            
            if transaction_type == 'wallet_transfer':
                return self.execute_wallet_transfer(data)
            
            if transaction_type == 'refund':
                direction = data.get('refund_direction')
                if not direction:
                    return {'error': 'Refund direction is required'}, 400
                
                data['entity_type'] = data.get(
                    'from_entity_type' if direction == 'incoming' else 'to_entity_type'
                )
                data['entity_id'] = None if data['entity_type'] == 'others' else data.get(
                    'from_entity_id' if direction == 'incoming' else 'to_entity_id'
                )
                data['mode'] = data.get(
                    'mode_for_to' if direction == 'incoming' and data['entity_type'] == 'others' 
                    else 'mode_for_from'
                )
            
            if data.get('entity_type') != 'others' and not data.get('entity_id'):
                return {'error': f"Entity ID is required for {data.get('entity_type')}"}, 400
            
            t = Transaction(
                ref_no=generate_ref_no(transaction_type),
                entity_type=data.get('entity_type'),
                entity_id=data.get('entity_id'),
                transaction_type=transaction_type,
                pay_type='refund' if transaction_type == 'refund' else data.get('pay_type'),
                mode=data.get('mode'),
                amount=float(amount),
                date=parse_transaction_date(data.get('transaction_date')),
                description=data.get('description'),
                particular_id=data.get('particular_id'),
                updated_by=getattr(g, 'username', 'system')
            )
            
            t.extra_data = {
                k: (None if v == '' else v) for k, v in {
                    'refund_direction': data.get('refund_direction'),
                    'deduct_from_account': data.get('deduct_from_account'),
                    'credit_to_account': data.get('credit_to_account'),
                    'from_entity_type': data.get('from_entity_type'),
                    'from_entity_id': None if data.get('from_entity_type') == 'others' else data.get('from_entity_id'),
                    'to_entity_type': data.get('to_entity_type'),
                    'to_entity_id': None if data.get('to_entity_type') == 'others' else data.get('to_entity_id'),
                    'mode_for_from': data.get('mode_for_from'),
                    'mode_for_to': data.get('mode_for_to'),
                }.items()
            }
            
            update_wallet_and_company(t)
            
            db.session.add(t)
            db.session.commit()
            
            return {
                'message': f'{transaction_type.capitalize()} created successfully',
                'transaction': get_transaction_payload(t)
            }, 201
        
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 400

    @check_permission()
    def put(self, transaction_id):
        t = Transaction.query.get(transaction_id)
        if not t:
            return {'error': 'Transaction not found'}, 404

        data = request.json

        try:
            amount = data.get('amount')
            if not amount or float(amount) <= 0:
                return {'error': 'Amount must be greater than 0'}, 400
            
            amount_changed = float(amount) != t.amount
            entities_changed = False
            mode_changed = False

            if t.transaction_type == 'wallet_transfer':
                entities_changed = (
                    data.get('from_entity_type') != t.extra_data.get('from_entity_type') or
                    data.get('from_entity_id') != t.extra_data.get('from_entity_id') or
                    data.get('to_entity_type') != t.extra_data.get('to_entity_type') or
                    data.get('to_entity_id') != t.extra_data.get('to_entity_id')
                )
            elif t.transaction_type == 'refund':
                old_from_mode = t.extra_data.get('mode_for_from')
                old_to_mode = t.extra_data.get('mode_for_to')
                new_from_mode = data.get('mode_for_from')
                new_to_mode = data.get('mode_for_to')
                mode_changed = (old_from_mode != new_from_mode or old_to_mode != new_to_mode)
            else: # For payment and receipt
                entities_changed = (
                    data.get('entity_type') != t.entity_type or
                    data.get('entity_id') != t.entity_id
                )
                mode_changed = data.get('mode') != t.mode
                
            # Revert old transaction logic. This is the crucial step.
            if amount_changed or entities_changed or mode_changed:
                revert_wallet_and_company(t)

            # Clear old flags before updating the transaction object
            t.extra_data.pop('company_adjusted', None)
            t.extra_data.pop('credited_entity', None)
            t.extra_data.pop('debited_entity', None)

            t.amount = float(amount)
            t.description = data.get('description')
            t.particular_id = data.get('particular_id')
            t.date = parse_transaction_date(data.get('transaction_date'))
            t.updated_by = getattr(g, 'username', 'system')

            if t.transaction_type == 'wallet_transfer':
                t.extra_data = {
                    'from_entity_type': data.get('from_entity_type'),
                    'from_entity_id': data.get('from_entity_id'),
                    'to_entity_type': data.get('to_entity_type'),
                    'to_entity_id': data.get('to_entity_id')
                }
                process_wallet_transfer(t)
            elif t.transaction_type == 'refund':
                direction = data.get('refund_direction')
                if not direction:
                    raise ValueError('Refund direction is required')
                
                t.extra_data = {
                    'refund_direction': direction,
                    'deduct_from_account': data.get('deduct_from_account'),
                    'credit_to_account': data.get('credit_to_account'),
                    'from_entity_type': data.get('from_entity_type'),
                    'from_entity_id': None if data.get('from_entity_type') == 'others' else data.get('from_entity_id'),
                    'to_entity_type': data.get('to_entity_type'),
                    'to_entity_id': None if data.get('to_entity_type') == 'others' else data.get('to_entity_id'),
                    'mode_for_from': data.get('mode_for_from'),
                    'mode_for_to': data.get('mode_for_to'),
                }

                t.entity_type = data.get('from_entity_type' if direction == 'incoming' else 'to_entity_type')
                t.entity_id = None if t.entity_type == 'others' else data.get(
                    'from_entity_id' if direction == 'incoming' else 'to_entity_id'
                )
                t.mode = data.get(
                    'mode_for_to' if direction == 'incoming' and t.entity_type == 'others'
                    else 'mode_for_from'
                )
                update_wallet_and_company(t)
            else: # payments and receipts
                t.entity_type = data.get('entity_type')
                t.entity_id = data.get('entity_id')
                t.pay_type = data.get('pay_type')
                t.mode = data.get('mode')
                update_wallet_and_company(t)

            db.session.commit()
            return {'message': 'Transaction updated'}, 200

        except ValueError as e:
            db.session.rollback()
            return {'error': str(e)}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 400


    @check_permission()
    def delete(self, transaction_id):
        t = Transaction.query.get(transaction_id)
        if not t:
            return {'error': 'Transaction not found'}, 404

        try:
            revert_wallet_and_company(t)
            db.session.delete(t)
            db.session.commit()
            return {'message': 'Transaction deleted and balances reverted'}, 200
        except ValueError as e:
            db.session.rollback()
            return {'error': str(e)}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 400
            
    def _export_transactions(self, transaction_type, format_type):
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search_query', '')
        
        query = Transaction.query.filter_by(transaction_type=transaction_type)
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date() + timedelta(days=1)
                query = query.filter(Transaction.date >= start, Transaction.date < end)
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD.'}, 400
        
        if search_query:
            search_pattern = f'%{search_query.lower()}%'
            query = query.outerjoin(Customer, (Transaction.entity_type == 'customer') & (Transaction.entity_id == Customer.id))\
                         .outerjoin(Agent, (Transaction.entity_type == 'agent') & (Transaction.entity_id == Agent.id))\
                         .outerjoin(Partner, (Transaction.entity_type == 'partner') & (Transaction.entity_id == Partner.id))\
                         .outerjoin(Particular, Transaction.particular_id == Particular.id)\
                         .filter(db.or_(
                            db.func.lower(Transaction.ref_no).like(search_pattern),
                            db.func.lower(Customer.name).like(search_pattern),
                            db.func.lower(Agent.name).like(search_pattern),
                            db.func.lower(Partner.name).like(search_pattern),
                            db.func.lower(Particular.name).like(search_pattern)
                         ))

        transactions = query.all()
        
        # This is the crucial part: format the data and call the correct export function
        formatted_data = [self._format_transaction_for_export(t) for t in transactions]

        if format_type == 'excel':
            return self.export_excel(data=formatted_data, transaction_type=transaction_type)
        elif format_type == 'pdf':
            return self.export_pdf(data=formatted_data, transaction_type=transaction_type)
        
        # Fallback in case of an invalid export format, though it should be caught earlier
        return {'error': 'Invalid export format'}, 400
    def execute_wallet_transfer(self, data):
        required = ['from_entity_type', 'from_entity_id', 'to_entity_type', 'to_entity_id', 'amount']
        if not all(data.get(field) for field in required):
            return {'error': 'Missing required fields for wallet transfer'}, 400

        t = Transaction(
            ref_no=generate_ref_no('wallet_transfer'),
            entity_type='wallet_transfer',
            entity_id=None,
            transaction_type='wallet_transfer',
            pay_type='wallet_transfer',
            mode='wallet',
            amount=float(data['amount']),
            date=parse_transaction_date(data.get('transaction_date', datetime.now())),
            description=data.get('description', ''),
            updated_by=getattr(g, 'username', 'system'),
            particular_id=data.get('particular_id'),
            extra_data={
                'from_entity_type': data['from_entity_type'],
                'from_entity_id': data['from_entity_id'],
                'to_entity_type': data['to_entity_type'],
                'to_entity_id': data['to_entity_id']
            }
        )
        
        process_wallet_transfer(t)
        db.session.add(t)
        db.session.commit()
        
        return {
            'message': 'Wallet transfer successful',
            'transaction': get_transaction_payload(t)
        }, 201

    def _format_transaction_for_export(self, transaction):
        base_data = {
            "Reference No": transaction.ref_no,
            "Date": transaction.date.strftime('%Y-%m-%d') if transaction.date else '',
        }
        
        if transaction.transaction_type == 'refund':
            direction = transaction.extra_data.get('refund_direction', '')
            base_data["Refund Direction"] = direction.capitalize()
        
        if transaction.transaction_type != 'wallet_transfer':
            base_data.update({
                "Entity Type": transaction.entity_type.capitalize() if transaction.entity_type else '',
                "Entity Name": get_entity_name(transaction.entity_type, transaction.entity_id),
            })
        
        if transaction.transaction_type == 'wallet_transfer':
            base_data.update({
                "From Entity": transaction.extra_data.get('from_entity_name', ''),
                "To Entity": transaction.extra_data.get('to_entity_name', ''),
                "Transfer Direction": f"{transaction.extra_data.get('from_entity_type', '').capitalize()} -> {transaction.extra_data.get('to_entity_type', '').capitalize()}"
            })
        
        base_data.update({
            "Particular": get_particular_name(transaction.particular_id),
            "Payment Type": transaction.pay_type.replace('_', ' ').title() if transaction.pay_type else '',
            "Mode": transaction.mode.capitalize() if transaction.mode else '',
            "Amount": transaction.amount,
            "Description": transaction.description,
        })
        
        return base_data

    def export_excel(self, data, transaction_type):
        return generate_export_excel(data=data, status=transaction_type, transaction_type=transaction_type)

    def export_pdf(self, data, transaction_type):
        title = f"{transaction_type.replace('_', ' ').title()} Transactions"
        total_amount = sum(row.get('Amount', 0) for row in data)
        summary_totals = {"Total Transactions": len(data), "Total Amount": total_amount}
        
        return generate_export_pdf(
            data=data,
            title=title,
            date_range_start=request.args.get('start_date', ''),
            date_range_end=request.args.get('end_date', ''),
            summary_totals=summary_totals,
            status=transaction_type
        )


class CompanyBalanceResource(Resource):
    @check_permission()
    def get(self, mode):
        last = CompanyAccountBalance.query.filter_by(mode=mode).order_by(CompanyAccountBalance.id.desc()).first()
        balance = last.balance if last else 0.0
        return {"mode": mode, "balance": balance}, 200