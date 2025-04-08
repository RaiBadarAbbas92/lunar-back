from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from typing import List, Dict
from datetime import datetime
import traceback  # For better error logging

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID') or '1GAGH6xAKaL5hfuPO-BE7_KOySTzv35BkhVga1Zp4t8Y'

def get_google_sheets_service():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'lunar-studio-user-query.json', scopes=SCOPES)
        return build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        print(f"Auth Error: {str(e)}")
        return None

def format_datetime(dt: datetime) -> str:
    """Helper function to format datetime objects"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""

def get_form_value(form, field_name):
    """Universal accessor for form data (works with both objects and dicts)"""
    if isinstance(form, dict):
        return form.get(field_name, '')
    return getattr(form, field_name, '')

def sync_forms_to_sheet(forms: List):
    service = get_google_sheets_service()
    if not service:
        return False

    # Use the actual sheet name we found in debug ('Sheet1')
    SHEET_NAME = 'Sheet1'
    RANGE_NAME = f"{SHEET_NAME}!A:H"

    try:
        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            body={}
        ).execute()

        # Prepare header row
        values = [['ID', 'Name', 'Email', 'Phone', 'Message', 'Company', 'Service', 'Created At']]
        
        # Process each form
        for form in forms:
            values.append([
                str(get_form_value(form, 'id')),
                get_form_value(form, 'name'),
                get_form_value(form, 'email'),
                get_form_value(form, 'phone_number'),
                get_form_value(form, 'message'),
                get_form_value(form, 'company'),
                get_form_value(form, 'service'),
                format_datetime(get_form_value(form, 'created_at'))
            ])

        # Update sheet with new data
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption='USER_ENTERED',
            body={'values': values}
        ).execute()

        return True

    except HttpError as error:
        error_details = error.content.decode() if hasattr(error, 'content') else str(error)
        print(f"Google Sheets API Error:\n{error_details}")
        return False
    except Exception as e:
        print(f"Unexpected Error: {str(e)}\n{traceback.format_exc()}")
        return False