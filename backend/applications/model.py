# applications/model.py
from datetime import datetime,date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itertools import chain

db = SQLAlchemy()

# association tables…
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)
user_permissions = db.Table('user_permissions',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permissions'
    id             = db.Column(db.Integer, primary_key=True)
    page_id        = db.Column(db.Integer, db.ForeignKey('pages.id',ondelete='CASCADE'), nullable=False)
    crud_operation = db.Column(db.String(10), nullable=False)   # 'read','write'
    __table_args__ = (db.UniqueConstraint('page_id','crud_operation', name='uq_page_crud'),)
    page = db.relationship('Page', back_populates='permissions')

class Role(db.Model):
    __tablename__ = 'roles'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')
    users       = db.relationship('User', back_populates='role')


class Page(db.Model):
    __tablename__ = 'pages'
    id    = db.Column(db.Integer, primary_key=True)
    name  = db.Column(db.String(100), unique=True, nullable=False)
    route = db.Column(db.String(100), unique=True, nullable=False)
    def to_dict(self):
        return {"id":self.id,"name":self.name,"route":self.route}
    permissions = db.relationship('Permission', back_populates='page', cascade='all, delete-orphan',passive_deletes=True)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(50), unique=True, nullable=False)
    full_name       = db.Column(db.String(100), nullable=False)
    password        = db.Column(db.String(128), nullable=False)
    last_seen       = db.Column(db.DateTime, default=datetime.now)
    role_id         = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    emp_id          = db.Column(db.Integer, unique=True, nullable=True)
    email           = db.Column(db.String(50), nullable=True)
    status          = db.Column(db.String(10), default="active", nullable=True)

    role            = db.relationship('Role', back_populates='users')
    permissions     = db.relationship('Permission', secondary=user_permissions, backref='users')
    session_version = db.Column(db.Integer, default=1, nullable=False)

    def set_password(self, pw):
        self.password = generate_password_hash(pw)
    def check_password(self, pw):
        return check_password_hash(self.password, pw)

    @property
    def is_admin(self):
        return bool(self.role and self.role.name == 'admin')

    def has_permission(self, perm_str):
        if self.is_admin:
            return True

        # Define a permission hierarchy mapping
        permission_order = {
            'full': 4,
            'modify': 3,
            'write': 2,
            'read': 1,
            'none': 0,
        }

        try:
            page, op = perm_str.split('.')
            required_level = permission_order.get(op, 0)
        except ValueError:
            return False

        effective_perms = self.effective_permissions
        for effective_perm_str in effective_perms:
            try:
                effective_page, effective_op = effective_perm_str.split('.')
                if effective_page == page and permission_order.get(effective_op, 0) >= required_level:
                    return True
            except ValueError:
                continue

        return False

    def validate(self):
        if not self.name: raise ValueError("Username required")
        if not self.full_name: raise ValueError("Full Name required")
        if not self.password: raise ValueError("Password required")
        if not self.role_id: raise ValueError("Role required")
            
    def to_jwt_claims(self):
        return {
            "perms": self.effective_permissions,
            "is_admin": self.is_admin,
            "session_version": self.session_version
        }

    @property
    def effective_permissions(self):
        if self.is_admin:
            # For admins, grant full permission on all pages
            return [f"{page.name.lower()}.full" for page in Page.query.all()]

        # Define a permission hierarchy mapping
        permission_order = {
            'full': 4,
            'modify': 3,
            'write': 2,
            'read': 1,
            'none': 0,
        }

        perms = {}
        
        # Process user overrides first
        for perm in self.permissions:
            page_name = perm.page.name.lower()
            perms[page_name] = perm.crud_operation

        # Process role permissions as a fallback, but do not override existing user permissions
        for perm in self.role.permissions:
            page_name = perm.page.name.lower()
            if page_name not in perms:
                perms[page_name] = perm.crud_operation
        
        # Only return the final, effective permissions as strings, ignoring 'none'
        return [f"{page}.{op}" for page, op in perms.items() if op != 'none']
    

    # Model for TravelAgency
class Particular(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships for both tickets and visas
    tickets = db.relationship('Ticket', backref='particular', cascade='all, delete-orphan', passive_deletes=True)
    visas = db.relationship('Visa', backref='particular', cascade='all, delete-orphan', passive_deletes=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='particular', foreign(Particular.id)==Attachment.parent_id)",
        backref='particular',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Particular {self.name}>"

class TravelLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships for both tickets and visas
    tickets = db.relationship('Ticket', backref='travel_location', cascade='all, delete-orphan', passive_deletes=True)
    visas = db.relationship('Visa', backref='travel_location', cascade='all, delete-orphan', passive_deletes=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='travel_location', foreign(TravelLocation.id)==Attachment.parent_id)",
        backref='travel_location',
        lazy=True,
        single_parent=True,
        viewonly=True 
    )
    def __repr__(self):
        return f"<TravelLocation {self.name}>"

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    contact = db.Column(db.String(40))
    email = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    wallet_balance = db.Column(db.Float, default=0.0)
    credit_limit = db.Column(db.Float, default=0.0)
    credit_used = db.Column(db.Float, default=0.0)
    
    tickets = db.relationship('Ticket', backref='customer', lazy=True)
    visas = db.relationship('Visa', backref='customer', lazy=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='customer', foreign(Customer.id)==Attachment.parent_id)",
        backref='customer',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Customer {self.name}>"

class Passenger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(40))
    passport_number = db.Column(db.String(40), nullable=True)
    active = db.Column(db.Boolean, default=True)
    salutation = db.Column(db.String(10), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    fathers_name = db.Column(db.String(100), nullable=True)
    mothers_name = db.Column(db.String(100), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)  
    passport_issue_date = db.Column(db.Date, nullable=True)
    passport_expiry = db.Column(db.Date, nullable=True)
    nationality = db.Column(db.String(50), nullable=True)
    
    tickets = db.relationship('Ticket', backref='passenger', lazy=True)
    visas = db.relationship('Visa', backref='passenger', lazy=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='passenger', foreign(Passenger.id)==Attachment.parent_id)",
        backref='passenger',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    __table_args__ = (
        db.UniqueConstraint('passport_number', name='uq_passport_not_null'),
    )
    def __repr__(self):
        return f"<Passenger {self.name}>"

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(40))
    email = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    wallet_balance = db.Column(db.Float, default=0.0)
    credit_limit = db.Column(db.Float, default=0.0)
    credit_balance = db.Column(db.Float, default=0.0)
    
    tickets = db.relationship('Ticket', backref='agent', lazy=True)
    visas = db.relationship('Visa', backref='agent', lazy=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='agent', foreign(Agent.id)==Attachment.parent_id)",
        backref='agent',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Agent {self.name}>"
        
class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(40))
    email = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    wallet_balance = db.Column(db.Float, default=0.0)
    allow_negative_wallet = db.Column(db.Boolean, default=False)
    
    tickets = db.relationship('Ticket', backref='partner', lazy=True)
    visas = db.relationship('Visa', backref='partner', lazy=True)
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='partner', foreign(Partner.id)==Attachment.parent_id)",
        backref='partner',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Partner {self.name}>"

# New model to manage visa types
class VisaType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    visas = db.relationship('Visa', backref='visa_type', lazy=True)

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='visa_type', foreign(VisaType.id)==Attachment.parent_id)",
        backref='visa_type',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<VisaType {self.name}>"
    
class TicketType(db.Model):
    __tablename__ = 'ticket_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    tickets = db.relationship('Ticket', backref='ticket_type', lazy=True)

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='ticket_type', foreign(TicketType.id)==Attachment.parent_id)",
        backref='ticket_type',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<TicketType {self.name}>"

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Core relationships
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    travel_location_id = db.Column(db.Integer, db.ForeignKey('travel_location.id'), nullable=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.id'), nullable=True)
    particular_id = db.Column(db.Integer, db.ForeignKey('particular.id'), nullable=True)
    description = db.Column(db.String(255))

    ticket_type_id = db.Column(db.Integer, db.ForeignKey('ticket_type.id'), nullable=True)
    # Ticket status & refund
    status = db.Column(db.String(20), default='booked')
    date = db.Column(db.Date, default=date.today)
    ref_no = db.Column(db.String(100), nullable=False)
    
    customer_charge = db.Column(db.Float, nullable=False, default=0.0)
    agent_paid = db.Column(db.Float, nullable=False, default=0.0)
    profit = db.Column(db.Float, nullable=False, default=0.0)

    customer_payment_mode = db.Column(db.String(20), nullable=True)
    agent_payment_mode = db.Column(db.String(20), nullable=True)

    # Refund breakdown
    customer_refund_amount = db.Column(db.Float, default=0)
    customer_refund_mode = db.Column(db.String(20))
    agent_recovery_amount = db.Column(db.Float, default=0)
    agent_recovery_mode = db.Column(db.String(20))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    updated_by = db.Column(db.String(100), default='system')
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='ticket', foreign(Ticket.id)==Attachment.parent_id)",
        backref='ticket',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Ticket {self.id} | {self.status} | {self.customer_charge} - {self.agent_paid} = {self.profit}>"

class Visa(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Core relationships
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    travel_location_id = db.Column(db.Integer, db.ForeignKey('travel_location.id'), nullable=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.id'), nullable=True)
    particular_id = db.Column(db.Integer, db.ForeignKey('particular.id'), nullable=True)
    description = db.Column(db.String(255))

    # Visa-specific foreign key
    visa_type_id = db.Column(db.Integer, db.ForeignKey('visa_type.id'), nullable=True)
    
    # Financials
    status = db.Column(db.String(20), default='booked')
    date = db.Column(db.Date, default=date.today)
    ref_no = db.Column(db.String(100), nullable=False)
    
    customer_charge = db.Column(db.Float, nullable=False, default=0.0)
    agent_paid = db.Column(db.Float, nullable=False, default=0.0)
    profit = db.Column(db.Float, nullable=False, default=0.0)

    customer_payment_mode = db.Column(db.String(20), nullable=True)
    agent_payment_mode = db.Column(db.String(20), nullable=True)

    # Refund breakdown
    customer_refund_amount = db.Column(db.Float, default=0)
    customer_refund_mode = db.Column(db.String(20))
    agent_recovery_amount = db.Column(db.Float, default=0)
    agent_recovery_mode = db.Column(db.String(20))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    updated_by = db.Column(db.String(100), default='system')

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='visa', foreign(Visa.id)==Attachment.parent_id)",
        backref='visa',
        lazy=True,
        single_parent=True,
        viewonly=True
    )

    def __repr__(self):
        return f"<Visa {self.id} | {self.visa_type.name if self.visa_type else 'N/A'} | {self.status}>"
    
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(100), unique=True, nullable=False)
    entity_type = db.Column(db.String(20), nullable=False)
    entity_id = db.Column(db.Integer)
    pay_type = db.Column(db.String(20), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.now)
    description = db.Column(db.String(255))
    particular_id = db.Column(db.Integer, db.ForeignKey('particular.id'))
    
    customer_refund_amount = db.Column(db.Float, default=0.0)
    agent_deduction_amount = db.Column(db.Float, default=0.0)
    mode_for_customer = db.Column(db.String(20), default='cash')
    mode_for_agent = db.Column(db.String(20), default='wallet')
    
    updated_by = db.Column(db.String(100), default='system')
    extra_data = db.Column(db.JSON, default={})
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='transaction', foreign(Transaction.id)==Attachment.parent_id)",
        backref='transaction',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Transaction {self.id} | {self.transaction_type} | {self.amount}>"

class CompanyAccountBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(20), nullable=False)
    credited_amount = db.Column(db.Float, default=0)
    credited_date = db.Column(db.DateTime, default=datetime.now())
    balance = db.Column(db.Float, default=0)

    ref_no = db.Column(db.String(100))
    transaction_type = db.Column(db.String(20))
    action = db.Column(db.String(20))
    updated_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now)
    def __repr__(self):
        return f"<CompanyAccountBalance {self.id} | {self.mode} | {self.balance}>"

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    particular_id = db.Column(db.Integer, db.ForeignKey('particular.id'), nullable=True)
    date = db.Column(db.Date, default=date.today)
    ref_no = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='booked')
    description = db.Column(db.String(255))
    
    customer_charge = db.Column(db.Float, nullable=False, default=0.0)
    customer_payment_mode = db.Column(db.String(20), nullable=True)
    
    customer_refund_amount = db.Column(db.Float, default=0.0)
    customer_refund_mode = db.Column(db.String(20))
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    updated_by = db.Column(db.String(100), default='system')
    
    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.parent_type=='service', foreign(Service.id)==Attachment.parent_id)",
        backref='service',
        lazy=True,
        single_parent=True,
        viewonly=True
    )
    def __repr__(self):
        return f"<Service {self.id} | {self.ref_no} | {self.status}>"

class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    parent_type = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)

    def __repr__(self):
        return f"<Attachment {self.id} | {self.file_name} for {self.parent_type}:{self.parent_id}>"


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)  # e.g. 2025/BAB/INV/0001
    entity_type = db.Column(db.String(20), nullable=False)  # 'customer', 'agent', 'partner'
    entity_id = db.Column(db.Integer, nullable=False)  # FK-like reference to entity
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled
    generated_date = db.Column(db.DateTime, default=datetime.now)
    pdf_path = db.Column(db.String(255), nullable=True)  # optional: store generated PDF path

    def __repr__(self):
        return f"<Invoice {self.invoice_number} | {self.entity_type} {self.entity_id} | {self.status}>"
