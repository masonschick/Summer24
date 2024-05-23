import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re

class ScrapeDKBases():
    """
    A class of functions to scrape MLB lines and odds on DraftKings Sportsbook.
    """

    def soup_setup(self, url):
        """
        Create a BeautifulSoup object from the given url.
        Should return <Response [200]>, unless there is an error.
        """
        response = requests.get(url)
        print(response)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup

    def team_cleanup(self, tm_name):
        """
        Takes an MLB team name from DraftKings and converts it to FanGraphs' format.
        """
        annoying = {'WAS Nationals':'WSN', 'CHI White Sox':'CHW', 'CHI Cubs':'CHC'}
        names = tm_name.split()
        if tm_name in annoying:
            city = annoying[tm_name]
        elif len(names[0]) == 2:
            city = f'{names[0]}{names[1][0]}'
        else:
            city = names[0]
        return city

    def mlb_ws(self):
        """
        Scrapes current World Series odds.
        
        Returns
        -------
        lamarca : nested dictionaries in the form of
        {<team abbreviation>: {'odds':<odds>, 'date_time':<datetime object with the current date and time>}, ...}
        """
        soup_today = self.soup_setup("https://sportsbook.draftkings.com/leagues/baseball/2003?category=team-futures&subcategory=world-series-2021")
        teams = []
        team_soup = soup_today.findAll('span', {'class':'sportsbook-outcome-cell__label'})
        for i in team_soup:
            city = self.team_cleanup(i.text)
            teams.append(city)
        
        odds = []
        odds_soup = soup_today.findAll('span', {'class':'sportsbook-odds american default-color'})
        for i in odds_soup:
            odd = i.text
            odd = int(odd.replace('+', ''))
            if odd > 0:
                pct = round(1 / ((odd/100) + 1), 4)
            else:
                pct = round(1 - (1 / ((-1*odd/100) + 1)), 4)
            odds.append(pct)
        
        lamarca = {}
        for i in range(len(teams)):
            lamarca[teams[i]] = {'odds':odds[i], 'date_time':datetime.now()}
        return lamarca

    def mlb_games(self):
        """
        Scrapes current MLB game odds.

        Returns
        -------
        games : dictionary containing teams, moneylines, totals, runlines and opponents.
        """
        games = {}
        market_ids = {'Game':493, '1st 5':729, 'TT':724}
        for cat in market_ids:
            dk_api = requests.get(f"https://sportsbook.draftkings.com//sites/US-NJ-SB/api/v4/eventgroups/88670847/categories/{market_ids[cat]}?format=json").json()
            if 'offerCategories' not in dk_api['eventGroup']:
                continue
            for i in dk_api['eventGroup']['offerCategories']:
                if 'offerSubcategoryDescriptors' in i:
                    dk_markets = i['offerSubcategoryDescriptors']
                    market_names = ['Game', 'Alternate Spread', 'Alternate Total', 'Team Totals',
                                    'Alternate Point Spread', 'Alternate Total Points',
                                    'Alternate Run Line', 'Alternate Total Runs',
                                    '1st 5 Innings', '1st 5 Innings - Moneyline',
                                    'Team Total Runs', 'Alt Total']
                    subcategoryIds = []
                    for i in dk_markets:
                        if i['name'] in market_names:
                            subcategoryIds.append(i['subcategoryId'])
                
                game_ids = {}
                for i in dk_api['eventGroup']['events']:
                    if i['eventStatus']['state'] != 'NOT_STARTED':
                        continue
                    next_id = False
                    if i['eventGroupName'] == 'MLB':
                        for x in game_ids:
                            if (game_ids[x]['home'] == i['teamName2']) & (game_ids[x]['away'] == i['teamName1']):
                                next_id = True
                    if not next_id:
                        game_ids[i['providerEventId']] = {'home':i['teamName2'], 'away':i['teamName1'],
                                                          'date': i['startDate']}
                            
                for ids in subcategoryIds:
                    dk_api = requests.get(f"https://sportsbook.draftkings.com//sites/US-NJ-SB/api/v4/eventgroups/88670847/categories/{market_ids[cat]}/subcategories/{ids}?format=json").json()
                    try:
                        dk_api['eventGroup']['offerCategories']
                    except:
                        continue
                    for i in dk_api['eventGroup']['offerCategories']:
                        if 'offerSubcategoryDescriptors' in i:
                            dk_markets = i['offerSubcategoryDescriptors']
                
                    for i in dk_markets:
                        if 'offerSubcategory' in i:
                            for j in i['offerSubcategory']['offers']:
                                for k in j:
                                    if 'providerEventId' in k:
                                        event = k['providerEventId']
                                    else:
                                        continue
                                    
                                    try:
                                        away_team = self.team_cleanup(game_ids[event]['away'])
                                        home_team = self.team_cleanup(game_ids[event]['home'])
                                    except:
                                        continue
                                        
                                    if away_team not in games:
                                        games[away_team] = {home_team: {'location': 0}}
                                    elif home_team not in games[away_team]:
                                        games[away_team][home_team] = {'location': 0}
                                    if home_team not in games:
                                        games[home_team] = {away_team: {'location': 1}}
                                    elif away_team not in games[home_team]:
                                        games[home_team][away_team] = {'location': 1}
                                                                            
                                    try:
                                        market = k['label']
                                        if '2nd Half' in market:
                                            continue
                                    except:
                                        continue
                                    
                                    periods = ['Game', '1st 5 Innings']
                                                                        
                                    if ('Spread' in market) | ('Run Line' in market):
                                        if 'spread' not in games[away_team][home_team]:
                                            games[away_team][home_team]['spread'] = {i: {} for i in periods}
                                            games[home_team][away_team]['spread'] = {i: {} for i in periods}
                                        
                                        for side in k['outcomes']:
                                            try:
                                                if self.name_cleanup(side['label'], sport, 'DK') == away_team:
                                                    games[away_team][home_team]['spread'][cat][side['line']] = side['oddsDecimal']
                                                elif self.name_cleanup(side['label'], sport, 'DK') == home_team:
                                                    games[home_team][away_team]['spread'][cat][side['line']] = side['oddsDecimal']
                                            except:
                                                pass
                                    elif 'Team Total' in market:
                                        if cat == 'TT':
                                            category = 'Game'
                                        else:
                                            category = cat
                                            
                                        if 'team total' not in games[away_team][home_team]:
                                            games[away_team][home_team]['team total'] = {i: {'over':{}, 'under':{}} for i in periods}
                                            games[home_team][away_team]['team total'] = {i: {'over':{}, 'under':{}} for i in periods}
                                        
                                        for side in k['outcomes']:
                                            try:
                                                if 'Touchdowns' in market:
                                                    continue
                                                if side['label'] == 'Over':
                                                    if self.name_cleanup(re.sub(':.+','', market), sport, 'DK') == away_team:
                                                        games[away_team][home_team]['team total'][category]['over'][side['line']] = side['oddsDecimal']
                                                    if self.name_cleanup(re.sub(':.+','', market), sport, 'DK') == home_team:                                                    
                                                        games[home_team][away_team]['team total'][category]['over'][side['line']] = side['oddsDecimal']
                                                elif side['label'] == 'Under':
                                                    if self.name_cleanup(re.sub(':.+','', market), sport, 'DK') == away_team:
                                                        games[away_team][home_team]['team total'][category]['under'][side['line']] = side['oddsDecimal']
                                                    if self.name_cleanup(re.sub(':.+','', market), sport, 'DK') == home_team:                                                    
                                                        games[home_team][away_team]['team total'][category]['under'][side['line']] = side['oddsDecimal']
                                            except Exception as e:
                                                print(e)
                                                pass
                                    elif 'Total' in market:
                                        if 'total' not in games[away_team][home_team]:
                                            games[away_team][home_team]['total'] = {i: {'over':{}, 'under':{}} for i in periods}
                                            games[home_team][away_team]['total'] = {i: {'over':{}, 'under':{}} for i in periods}
                                        
                                        for side in k['outcomes']:
                                            try:
                                                if side['label'] == 'Over':
                                                    games[away_team][home_team]['total'][cat]['over'][side['line']] = side['oddsDecimal']
                                                    games[home_team][away_team]['total'][cat]['over'][side['line']] = side['oddsDecimal']
                                                elif side['label'] == 'Under':
                                                    games[away_team][home_team]['total'][cat]['under'][side['line']] = side['oddsDecimal']
                                                    games[home_team][away_team]['total'][cat]['under'][side['line']] = side['oddsDecimal']
                                            except:
                                                pass
                                    elif 'Moneyline' in market:
                                        if 'moneyline' not in games[away_team][home_team]:
                                            games[away_team][home_team]['moneyline'] = {}
                                            games[home_team][away_team]['moneyline'] = {}
                                        
                                        for side in k['outcomes']:
                                            try:
                                                if self.name_cleanup(side['label'], sport, 'DK') == away_team:
                                                    games[away_team][home_team]['moneyline'][cat] = side['oddsDecimal']
                                                elif self.name_cleanup(side['label'], sport, 'DK') == home_team:
                                                    games[home_team][away_team]['moneyline'][cat] = side['oddsDecimal']
                                            except:
                                                pass
        return games

# Instantiate the class
scraper = ScrapeDKBases()

# Call mlb_ws method and display the output
world_series_odds = scraper.mlb_ws()
print(world_series_odds)

# Call mlb_games method and display the output
mlb_game_odds = scraper.mlb_games()
print(mlb_game_odds)
