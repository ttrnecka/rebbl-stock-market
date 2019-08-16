"""REBBL Net api agent modul"""
import requests

class REBBL_API:
    """BB2 api agent"""
    BASE_URL = "https://rebbl.net/api/v2/"
    
    def slim_round(self, league, season, round):
        url = self.__class__.BASE_URL +"league/"+str(league)+"/"+str(season)+"/slim/"+str(round)
        r = requests.get(url=url)
        data = r.json()
        return data
