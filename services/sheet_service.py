"""Imperiumr Sheet Service helpers"""
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

ROOT = os.path.dirname(__file__)

# use CREDS to create a client to interact with the Google Drive API
SCOPE = ['https://spreadsheets.google.com/feeds']
CREDS = ServiceAccountCredentials.from_json_keyfile_name(
    os.path.join(ROOT, '../config/client_secret.json'), SCOPE)


class SheetService:
    """Namespace class"""
    #SPREADSHEET_ID = "1asnfGr4M1ec2IW46nv4md5glT2-Eq0j60iOuYsVsVeE"
    #season 11
    SPREADSHEET_ID="14_AbpkuAYWUw5cx_BmWVN91G_MgRCRUMWKSKIuUaTlg"
    # dev spreadsheet below
    #SPREADSHEET_ID = "1asnfGr4M1ec2IW46nv4md5glT2-Eq0j60iOuYsVsVeE"
    MAIN_SHEET="Current Team Values"

    _stocks = None

    @classmethod
    def stocks(cls, refresh=False):
        """Returns torunaments from the sheet"""
        if not cls._stocks or refresh:
            client = gspread.authorize(CREDS)
            sheet = client.open_by_key(cls.SPREADSHEET_ID).worksheet(cls.MAIN_SHEET)
            cls._stocks = sheet.get_all_records()
        return cls._stocks

#if __name__ == "__main__":
