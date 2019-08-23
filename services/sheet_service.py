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
    #season 12
    SPREADSHEET_ID="1UuHysgRw2t1PzlEnqM_8QDACm0eX4uDe8LtO9scIhGQ"
    # dev spreadsheet below
    #SPREADSHEET_ID = "1-f4tu9Hs0OXlnoBrwLRktmddcy_uKHGZQzg9ZtXdGFg"
    MAIN_SHEET="Current Team Values"
    IMPORT_SHEET="Bot Import"

    _stocks = None

    header = {
        "division":"division",
        "round":"round",
        "match_uuid":"match_uuid",
        "homeCoachId":"homeCoachId",
        "homeCoachName":"homeCoachName",
        "homeTeamId":"homeTeamId",
        "homeTeamName":"homeTeamName",
        "homeTeamRace":"homeTeamRace",
        "homeScore":"homeScore",
        "awayCoachId":"awayCoachId",
        "awayCoachName":"awayCoachName",
        "awayTeamId":"awayTeamId",
        "awayTeamName":"awayTeamName",
        "awayTeamRace":"awayTeamRace",
        "awayScore":"awayScore"
    }

    @classmethod
    def stocks(cls, refresh=False):
        """Returns torunaments from the sheet"""
        if not cls._stocks or refresh:
            client = gspread.authorize(CREDS)
            sheet = client.open_by_key(cls.SPREADSHEET_ID).worksheet(cls.MAIN_SHEET)
            cls._stocks = sheet.get_all_records()
        return cls._stocks

    @classmethod
    def update_matches(cls, matches):
        matches_to_export = [cls.__match_to_dict(match) for match in matches]
        #insert header
        matches_to_export.insert(0, cls.header)
        # turn dict to list
        matches_to_export = [list(match.values()) for match in matches_to_export]

        client = gspread.authorize(CREDS)
        sheet = client.open_by_key(cls.SPREADSHEET_ID)
        sheet.values_update(
            f'{cls.IMPORT_SHEET}!A1', 
            params={'valueInputOption': 'RAW'}, 
            body={'values': matches_to_export}
        )

    @classmethod
    def __match_to_dict(cls,match):
        match_d = {}
        for key in cls.header.keys():
            match_d[key] = getattr(match, key)
        match_d["homeTeamName"] = match_d["homeTeamName"].strip()
        match_d["awayTeamName"] = match_d["awayTeamName"].strip()
        return match_d

#if __name__ == "__main__":
