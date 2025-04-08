import os
import json
from typing import List, Dict, Union
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_NAME = 'Sheet1'  # Fallback if 'lunar' doesn't exist

def get_google_sheets_service():
    """Initialize Google Sheets service using Vercel env variables"""
    try:
        creds_json = os.getenv('GOOGLE_CREDENTIALS')
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
            
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=SCOPES
        )
        return build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        print(f"Service initialization failed: {str(e)}")
        return None

def format_datetime(dt: datetime) -> str:
    """Safe datetime formatter"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""

def get_form_value(form: Union[Dict, object], field: str) -> str:
    """Universal field accessor for both dicts and objects"""
    try:
        if isinstance(form, dict):
            return str(form.get(field, ''))
        return str(getattr(form, field, ''))
    except Exception:
        return ''

def sync_forms_to_sheet(forms: List[Union[Dict, object]]) -> bool:
    """Main sync function optimized for Vercel"""
    try:
        # Initialize service
        service = get_google_sheets_service()
        if not service:
            return False

        spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')
        if not spreadsheet_id:
            print("GOOGLE_SHEET_ID not set")
            return False

        # Determine sheet name
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(title))"
        ).execute()
        
        sheets = [s['properties']['title'] for s in sheet_metadata.get('sheets', [])]
        sheet_name = 'lunar' if 'lunar' in sheets else DEFAULT_SHEET_NAME
        range_name = f"{sheet_name}!A:H"

        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            body={}
        ).execute()

        # Prepare data
        headers = ['ID', 'Name', 'Email', 'Phone', 'Message', 'Company', 'Service', 'Created At']
        values = [headers]
        
        for form in forms:
            values.append([
                get_form_value(form, 'id'),
                get_form_value(form, 'name'),
                get_form_value(form, 'email'),
                get_form_value(form, 'phone_number'),
                get_form_value(form, 'message'),
                get_form_value(form, 'company'),
                get_form_value(form, 'service'),
                format_datetime(
                    get_form_value(form, 'created_at') if isinstance(get_form_value(form, 'created_at'), datetime)
                    else None
                )
            ])

        # Batch update
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption='USER_ENTERED',
            body={'values': values}
        ).execute()

        return True

    except HttpError as error:
        error_details = getattr(error, 'content', str(error))
        print(f"Google Sheets API Error: {error_details}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False
