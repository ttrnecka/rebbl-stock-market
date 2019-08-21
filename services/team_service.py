"""TeamService helpers"""
import json
from models.data_models import Stock
from models.base_model import db
from .sheet_service import SheetService

class TeamService:
    @classmethod
    def get_game(cls, team_name, round_n=1):
        team_matches = cls.get_team_matches(team_name)

        #sort by round
        #team_matches = sorted(team_matches, key=lambda t: t['round'])

        # return first unplayed match
        for match in team_matches:
            if match['round'] == round_n:
                return match

        return  None

    @classmethod
    def get_team_matches(cls, team_name):
        app = db.get_app()
        file_name = app.config['MATCH_FILE']

        matches = []
        with open(file_name) as file:  
            matches = json.loads(file.read())

        team_matches = [match for match in matches if match['awayTeamName'].strip() == team_name or match['homeTeamName'].strip() == team_name]
        return team_matches