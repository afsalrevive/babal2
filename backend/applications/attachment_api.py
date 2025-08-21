# applications/attachment_api.py
from flask import request, abort, send_file, current_app
from flask_restful import Resource
from applications.model import db, Attachment, Customer, Agent, Partner, Transaction, Ticket, Service, Particular, TravelLocation, Passenger, VisaType
from applications.utils import check_permission
import os
from werkzeug.utils import secure_filename
from datetime import datetime


# Model map for fetching entity/transaction details
MODEL_MAP = {
    'customer': Customer,
    'agent': Agent,
    'partner': Partner,
    'passenger': Passenger,
    'particular': Particular,
    'travel_location': TravelLocation,
    'visa_type' : VisaType,
    'ticket': Ticket,
    'service': Service,
    'transaction': Transaction
}

def get_upload_path(parent_type, parent_id):
    # This function is unchanged and correctly creates the directory structure
    base_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], parent_type)
    
    if parent_type == 'entity':
        entity = MODEL_MAP['customer'].query.get(parent_id) or \
                 MODEL_MAP['agent'].query.get(parent_id) or \
                 MODEL_MAP['partner'].query.get(parent_id) or \
                 MODEL_MAP['passenger'].query.get(parent_id)
        if entity:
            entity_type = entity.__tablename__
            base_folder = os.path.join(base_folder, entity_type)
        else:
            abort(404, "Parent entity not found.")

    elif parent_type == 'transaction':
        transaction = MODEL_MAP['transaction'].query.get(parent_id)
        if transaction:
            txn_type = transaction.transaction_type
            base_folder = os.path.join(base_folder, txn_type)
        else:
            abort(404, "Parent transaction not found.")
            
    os.makedirs(base_folder, exist_ok=True)
    return base_folder
    

class AttachmentResource(Resource):
    def __init__(self, **kwargs):
        super().__init__()

    @check_permission()
    def get(self, parent_type=None, parent_id=None, attachment_id=None):
        if attachment_id:
            attachment = Attachment.query.get(attachment_id)
            if not attachment:
                abort(404, "Attachment not found")
            
            # Reconstruct the absolute file path for serving
            absolute_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)
            
            if not os.path.exists(absolute_file_path):
                abort(404, "File not found on disk.")
            
            return send_file(absolute_file_path, as_attachment=True, download_name=attachment.file_name)
        
        # The rest of the get method remains the same
        if parent_type and parent_id:
            attachments = Attachment.query.filter_by(parent_type=parent_type, parent_id=parent_id).all()
            return [{"id": a.id, "file_name": a.file_name} for a in attachments], 200
        
        abort(400, "Invalid request. Specify parent_type/id or attachment_id.")
    
    @check_permission()
    def post(self, parent_type, parent_id):
        if 'file' not in request.files:
            abort(400, "No file part in the request")
        
        file = request.files['file']
        if file.filename == '':
            abort(400, "No selected file")

        if file:
            # The upload path is still absolute for saving the file
            upload_path = get_upload_path(parent_type, parent_id)
            original_filename = secure_filename(file.filename)
            prefix = ""

            model = MODEL_MAP.get(parent_type)
            if model:
                parent_obj = model.query.get(parent_id)
                if parent_obj:
                    if hasattr(parent_obj, 'ref_no'):
                        sanitized_ref_no = parent_obj.ref_no.replace('/', '-')
                        prefix = f"{sanitized_ref_no}_"
                    elif hasattr(parent_obj, 'name'):
                        sanitized_name = parent_obj.name.replace(' ', '_')
                        prefix = f"{sanitized_name}_"

            unique_filename = f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
            
            # Create the absolute file path to save the file
            absolute_file_path = os.path.join(upload_path, unique_filename)
            file.save(absolute_file_path)
            
            # Here's the key change: store the path relative to the UPLOAD_FOLDER
            relative_file_path = os.path.relpath(absolute_file_path, current_app.config['UPLOAD_FOLDER'])
            
            new_attachment = Attachment(
                file_name=original_filename,
                file_path=relative_file_path,  # Save the relative path
                parent_type=parent_type,
                parent_id=parent_id,
            )
            db.session.add(new_attachment)
            db.session.commit()
            
            return {"message": "File uploaded successfully", "id": new_attachment.id}, 201

    @check_permission()
    def delete(self, attachment_id):
        attachment = Attachment.query.get(attachment_id)
        if not attachment:
            abort(404, "Attachment not found")

        try:
            db.session.delete(attachment)
            db.session.commit()
            
            # Reconstruct the absolute file path for deletion
            absolute_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)
            
            if os.path.exists(absolute_file_path):
                os.remove(absolute_file_path) 
            
            return {"message": "Attachment deleted"}, 200
        except OSError as e:
            db.session.rollback()
            abort(500, f"Failed to delete file from disk: {str(e)}")
        except Exception as e:
            db.session.rollback()
            abort(500, f"Failed to delete attachment: {str(e)}")