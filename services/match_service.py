"""MatchService helpers"""
import json
from sqlalchemy import or_, not_
from models.data_models import Stock, Match
from models.base_model import db
from .sheet_service import SheetService

class MatchService:
    @classmethod
    def get_game(cls, team_name, round_n=1):
        team_matches = cls.get_team_matches(team_name)

        for match in team_matches:
            if match.round == round_n:
                return match

        return  None

    @classmethod
    def get_team_matches(cls, team_name):
        return Match.query.filter(or_(Match.awayTeamName.ilike(f'%{team_name}%'), Match.homeTeamName.ilike(f'%{team_name}%'))).all()

    @classmethod
    def import_matches(cls, matches):
        for match in matches:
            match_instance = Match.query.filter_by(homeTeamName=match['homeTeamName'], awayTeamName=match['awayTeamName'], division=match['division'], round=match['round']).one_or_none()
            if not match_instance:
                match_instance = Match(**match)
                db.session.add(match_instance)
            else:
                match_instance.update(**match)
        db.session.commit()

    @classmethod
    def played(cls):
        return Match.query.filter(Match.match_uuid != None, not_(Match.division.ilike('%MNG%'))).all()