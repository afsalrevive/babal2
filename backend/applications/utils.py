from functools import wraps
from flask import abort,request
from flask_jwt_extended import jwt_required, get_jwt
from applications.model import User

from flask import request, abort, g
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt

def check_permission():
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()

            # Define a permission hierarchy mapping
            permission_order = {
                'full': 4,
                'modify': 3,
                'write': 2,
                'read': 1,
                'none': 0,
            }

            # Store user info for downstream use (e.g., audit logs)
            g.user_id = claims.get("sub")
            g.username = claims.get("username", "system")

            # Admin bypass
            if claims.get('is_admin'):
                return fn(*args, **kwargs)

            # Validate normal users
            resource = request.headers.get('X-Resource', '').lower()
            operation = request.headers.get('X-Operation', '').lower()

            if not resource or not operation:
                abort(400, "Missing permission headers")

            perms = claims.get("perms", [])
            
            has_access = False
            required_level = permission_order.get(operation, 0)
            
            if required_level > 0:
                for perm_string in perms:
                    try:
                        perm_resource, perm_op = perm_string.split('.')
                        if perm_resource == resource and permission_order.get(perm_op, 0) >= required_level:
                            has_access = True
                            break
                    except ValueError:
                        continue

            if has_access:
                return fn(*args, **kwargs)

            abort(403, f"Requires {resource}.{operation}")
        return wrapper
    return decorator


def require_admin(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if not claims.get("is_admin"):
            abort(403, description="Admin access required")
        return fn(*args, **kwargs)
    return wrapper
def get_perms_for_audit(user_id):
    user = User.get(user_id)
    return user.effective_permissions
def serialize_entity(entity):
    return {col.name: getattr(entity, col.name) for col in entity.__table__.columns}

def get_user_payload(user):
    """Serialize user with all details and effective permissions"""
    return {
        "id": user.id,
        "name": user.name,
        "full_name": user.full_name,
        "email": user.email,
        "emp_id": user.emp_id,
        "status": user.status,
        "last_seen": user.last_seen.isoformat() if user.last_seen else None,
        "role": {
            "id": user.role.id,
            "name": user.role.name
        } if user.role else None,
        "perms": user.effective_permissions,
        "session_version": user.session_version,
        "is_admin": user.is_admin
    }

def normalize(name: str) -> str:
    n = name.lower()
    return n