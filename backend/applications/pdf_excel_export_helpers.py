# applications/pdf_excel_export_helpers.py
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
from flask import send_file, request
import pandas as pd
import re

def generate_export_pdf(data, title, date_range_start, date_range_end, summary_totals=None, exclude_columns=None, status=None):
    """
    A reusable function to generate a PDF export with dynamic headers, data, and summary.
    """
    try:
        pdf = FPDF(orientation='L', unit='mm', format='A3')  # Increased to A3 to provide more space
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Filter data based on excluded columns
        if exclude_columns and data:
            data = [
                {k: v for k, v in row.items() if k not in exclude_columns}
                for row in data
            ]
        
        if not data:
            # Handle empty data case
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, title, 0, 1, 'C')
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 8, f"Date Range: {date_range_start} to {date_range_end}", 0, 1, 'C')
            pdf.cell(0, 10, "No data available in this range.", 0, 1, 'C')
            output = BytesIO()
            pdf.output(output, 'S').encode('latin1')
            output.seek(0)
            return send_file(output, mimetype='application/pdf', as_attachment=True, download_name=f"{status}_export_{datetime.now().strftime('%Y%m%d')}.pdf")

        headers = list(data[0].keys())
        
        # Title and date range
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, title, 0, 1, 'C')
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, f"Date Range: {date_range_start} to {date_range_end}", 0, 1, 'C')
        pdf.ln(5)
        
        printable_width = pdf.w - 2 * pdf.l_margin
        col_width = printable_width / len(headers)
        
        # New robust header rendering logic
        pdf.set_fill_color(70, 130, 180)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 9)
        
        # First pass for headers: calculate max height for wrapping
        header_heights = []
        max_header_height = 10
        for header in headers:
            lines = pdf.multi_cell(col_width, 5, header, border=0, align='C', split_only=True)
            header_heights.append(len(lines) * 5)
            max_header_height = max(max_header_height, len(lines) * 5)
            
        # Second pass for headers: render with uniform height
        y_start = pdf.get_y()
        x_pos = pdf.l_margin
        for i, header in enumerate(headers):
            pdf.set_xy(x_pos, y_start)
            pdf.cell(col_width, max_header_height, '', border=1, fill=True)
            
            lines = pdf.multi_cell(col_width, 5, header, border=0, align='C', split_only=True)
            text_height = len(lines) * 5
            y_text = y_start + (max_header_height - text_height) / 2
            
            pdf.set_xy(x_pos, y_text)
            pdf.multi_cell(col_width, 5, header, border=0, align='C')
            
            x_pos += col_width
        
        pdf.set_y(y_start + max_header_height)
        
        # Data rows
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('', '', 9)

        for row in data:
            max_row_height = 10
            
            temp_pdf = FPDF(orientation='L', unit='mm', format='A3')
            temp_pdf.set_font('Arial', '', 9)
            
            for key in headers:
                value = row.get(key, '')
                if isinstance(value, (int, float)):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                
                lines = temp_pdf.multi_cell(col_width, 5, value_str, border=0, align='C', split_only=True)
                cell_height = len(lines) * 5
                max_row_height = max(max_row_height, cell_height)

            if pdf.get_y() + max_row_height > pdf.h - 20:
                pdf.add_page(orientation='L')
                # Re-render headers on new page
                y_start_new_page = pdf.get_y()
                x_pos_new_page = pdf.l_margin
                for i, header in enumerate(headers):
                    pdf.set_xy(x_pos_new_page, y_start_new_page)
                    pdf.cell(col_width, max_header_height, '', border=1, fill=True)
                    lines = pdf.multi_cell(col_width, 5, header, border=0, align='C', split_only=True)
                    text_height = len(lines) * 5
                    y_text = y_start_new_page + (max_header_height - text_height) / 2
                    pdf.set_xy(x_pos_new_page, y_text)
                    pdf.multi_cell(col_width, 5, header, border=0, align='C')
                    x_pos_new_page += col_width
                pdf.set_y(y_start_new_page + max_header_height)
                
            y_start_of_row = pdf.get_y()
            x_pos = pdf.l_margin

            for key in headers:
                value = row.get(key, '')
                if isinstance(value, (int, float)):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)
                
                pdf.set_xy(x_pos, y_start_of_row)
                pdf.cell(col_width, max_row_height, '', border=1, ln=0)
                
                lines = pdf.multi_cell(col_width, 5, value_str, border=0, align='C', split_only=True)
                text_height = len(lines) * 5
                y_text = y_start_of_row + (max_row_height - text_height) / 2
                
                pdf.set_xy(x_pos, y_text)
                pdf.multi_cell(col_width, 5, value_str, border=0, align='C')
                
                x_pos += col_width
            
            pdf.set_y(y_start_of_row + max_row_height)
        
        # Summary section
        if summary_totals:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            for label, total in summary_totals.items():
                if isinstance(total, (int, float)):
                    pdf.cell(0, 8, f"{label}: {total:.2f}", 0, 1, 'R')
                else:
                    pdf.cell(0, 8, f"{label}: {total}", 0, 1, 'R')
            
        pdf.set_y(-15)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 0, 'C')

        output = BytesIO()
        output.write(pdf.output(dest='S').encode('latin1'))
        output.seek(0)

        download_name = f"{status}_{title.replace(' ', '_').lower()}_export_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name=download_name)

    except Exception as e:
        print(f"PDF generation failed: {e}")
        return {'error': f'PDF export failed: {str(e)}'}, 500

def generate_export_excel(data, status, transaction_type=None):
    """
    A reusable function to generate an Excel export.
    """
    try:
        if not data:
            # Handle empty data case for Excel
            data = [{'Message': 'No data available in this range.'}]

        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            sheet_name = transaction_type or status
            sheet_name = re.sub(r'[\\/*?:[\]]', '', sheet_name)
            if len(sheet_name) > 31:
                sheet_name = sheet_name[:31]
            
            df.to_excel(writer, sheet_name=sheet_name, index=False, float_format="%.2f")
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            header_format = workbook.add_format({
                'bold': True, 
                'border': 1,
                'bg_color': '#4472C4',
                'font_color': 'white'
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            for idx, col in enumerate(df.columns):
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                ) + 2
                worksheet.set_column(idx, idx, max_len)
        
        output.seek(0)
        
        file_prefix = transaction_type if transaction_type else status
        download_name = f'{file_prefix}_export_{datetime.now().strftime("%Y%m%d")}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        return {'error': f'Excel export failed: {str(e)}'}, 500