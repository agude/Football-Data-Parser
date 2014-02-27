#!/usr/bin/env python3

import json
from bs4 import BeautifulSoup, SoupStrainer
from copy import deepcopy
from raw_data_parsers.parse_game_info import convert_time, convert_weather, convert_duration, convert_overunder, convert_vegas_line, convert_stadium
from raw_data_parsers.parse_title_info import convert_title_teams, convert_title_date
from raw_data_parsers.parse_team_stats import convert_rush_info, convert_pass_info, convert_sack_info, convert_fumble_info, convert_penalty_info
from data_helpers.team_list import names_to_code

from play_by_play import PlayByPlay


class Converter:

    def __init__(self, file_name):
        """Given the file name of a raw data file, opens it and converts it to
        JSON.

        args:
            file_name: A string containing the name of a file to open
        """
        # Set up some internal variables
        self.home_team = None
        self.away_team = None
        self.home_players = set([])
        self.away_players = set([])

        # Initialize the dictionary to convert to JSON
        self.__init_json()

        # Set up Strainers
        self.__set_strainers()

        # Open the file and load the soup
        self.file_name = file_name
        self.soups = {}
        with open(self.file_name) as file_handle:
            cont = file_handle.read()

        # Make the Soups
        for key, value in self.strainers.items():
            self.soups[key] = BeautifulSoup(cont, parse_only=value)

        # Parse the various tables
        self.__parse_title()
        self.__parse_officials()
        self.__parse_game_info()
        self.__parse_team_stats()
        self.__parse_starter()

        # Parse all players onto teams, the starter list isn't enough
        self.__get_all_players()

        # Parse Play-by-play
        self.pbp = PlayByPlay(self.soups["pbp_data"])
        self.json["plays"] = self.pbp.json

    def __init_json(self):
        """ Initialize the dictionary for the output JSON. """
        self.json = {
                "home team": None,
                "away team": None,
                "venue": None,
                "datetime": None,
                "weather": None,
                "betting": None,
                "officials": None,
                "team stats": {},
                "plays": []
                }
        self.json["venue"] = {
                "stadium": None,
                "dome": None,
                "surface": None,
                "attendance": None
                }
        self.json["datetime"] = {
                "date": None,
                "start time": None,
                "duration": None
                }
        self.json["betting"] = {
                "winner": None,
                "speard": None,
                "over under": None
                }
        self.json["players"] = {
                "home": {},
                "away": {}
                }
        teamstats = {
                "first downs": None,
                "rush": {
                    "plays": None,
                    "yards": None,
                    "touchdowns": None,
                    },
                "pass": {
                    "plays": None,
                    "yards": None,
                    "touchdowns": None,
                    "successful": None,
                    "interceptions": None
                    },
                "sacks": {
                    "plays": None,
                    "yards": None
                    },
                "fumbles": {
                    "plays": None,
                    "lost": None
                    },
                "penalties": {
                    "plays": None,
                    "yards": None
                    }
                }
        # We use deep copy so that we can uniquely set values in each, instead
        # of having them linked.
        self.json["team stats"]["home"] = deepcopy(teamstats)
        self.json["team stats"]["away"] = deepcopy(teamstats)

    def __set_strainers(self):
        """ Set up a list of hard coded SoupStrainers. """
        self.strainers = {}
        self.strainers["title"] = SoupStrainer("title")
        self.strainers["game_info"] = SoupStrainer(id="game_info")
        self.strainers["ref_info"] = SoupStrainer(id="ref_info")
        self.strainers["team_stats"] = SoupStrainer(id="team_stats")
        self.strainers["pbp_data"] = SoupStrainer(id="pbp_data")
        self.strainers["starters"] = SoupStrainer("table", id="")
        self.strainers["def_stats"] = SoupStrainer("table", id="def_stats")
        self.strainers["off_stats"] = SoupStrainer("table", id="skill_stats")
        self.strainers["kick_stats"] = SoupStrainer("table", id="kick_stats")

    def __parse_title(self):
        """ Parse the title tag from the HTML. This sets the two teams and the
        date."""
        soup = self.soups["title"]
        text = soup.find("title").get_text(strip=True)
        teams = text.split('-')[0]
        fulldate = text.split('-')[1]
        # Parse teams to codes
        (home, away) = convert_title_teams(teams)
        self.json["home team"] = home
        self.home_team = home
        self.json["away team"] = away
        self.away_team = away
        # Parse time
        self.json["datetime"]["date"] = convert_title_date(fulldate)

    def __parse_officials(self):
        """ Set up the officials dictionary and add it to self.json """
        ref_dict = {}
        soup = self.soups["ref_info"]
        # Find each row of the table
        rows = soup.find_all("tr")
        for row in rows:
            # Find each column of the table
            cols = row.find_all("td")
            if cols:  # This if removes the header
                # Extract the position and name of the referee
                tmp_pos = cols[0].get_text(strip=True)
                tmp_name = cols[1].get_text(strip=True)
                # Lowercase the position, and remove newlines in the name
                pos = tmp_pos.lower()
                name = tmp_name.replace('\n', ' ')
                # Insert into our dictionary
                ref_dict[pos] = name

        # Insert the finished dictionary into the json
        self.json["officials"] = ref_dict

    def __parse_team_stats(self):
        """ Set up the team stats dictionaries and add it to self.json """
        soup = self.soups["team_stats"]
        # Find each row of the table
        rows = soup.find_all("tr")
        home_dict = self.json["team stats"]["home"]
        away_dict = self.json["team stats"]["away"]
        for row in rows:
            # Find each column of the table
            cols = row.find_all("td")
            if cols:  # This if removes the header
                # Extract the key and both the home and away team values
                key = cols[0].get_text(strip=True)
                tmp_away = cols[1].get_text(strip=True)
                tmp_home = cols[2].get_text(strip=True)
                if key == "First downs":
                    away_dict["first downs"] = int(tmp_away)
                    home_dict["first downs"] = int(tmp_home)
                elif key == "Rush-yards-TDs":
                    away_dict["rush"] = convert_rush_info(tmp_away)
                    home_dict["rush"] = convert_rush_info(tmp_home)
                elif key == "Comp-Att-Yd-TD-INT":
                    away_dict["pass"] = convert_pass_info(tmp_away)
                    home_dict["pass"] = convert_pass_info(tmp_home)
                elif key == "Sacked-yards":
                    away_dict["sacks"] = convert_sack_info(tmp_away)
                    home_dict["sacks"] = convert_sack_info(tmp_home)
                elif key == "Fumbles-lost":
                    away_dict["fumbles"] = convert_fumble_info(tmp_away)
                    home_dict["fumbles"] = convert_fumble_info(tmp_home)
                elif key == "Penalties-yards":
                    away_dict["penalties"] = convert_penalty_info(tmp_away)
                    home_dict["penalties"] = convert_penalty_info(tmp_home)

    def __parse_game_info(self):
        """ Set up the game info dictionary and add it to self.json """
        soup = self.soups["game_info"]
        # Find each row of the table
        rows = soup.find_all("tr")
        for row in rows:
            # Find each column of the table
            cols = row.find_all("td")
            if cols:  # This if removes the header
                # Extract the key and value
                tmp_key = cols[0].get_text(strip=True)
                tmp_value = cols[1].get_text(strip=True)
                if tmp_key == "Stadium":
                    (stad, dome) = convert_stadium(tmp_value)
                    self.json["venue"]["stadium"] = stad
                    self.json["venue"]["dome"] = dome
                elif tmp_key == "Start Time":
                    self.json["datetime"]["start time"] = convert_time(tmp_value)
                elif tmp_key == "Surface":
                    self.json["venue"]["surface"] = tmp_value
                elif tmp_key == "Duration":
                    self.json["datetime"]["duration"] = convert_duration(tmp_value)
                elif tmp_key == "Attendance":
                    # We need to replace commas for int to work
                    self.json["venue"]["attendance"] = int(tmp_value.replace(',', ''))
                elif tmp_key == "Weather":
                    self.json["weather"] = convert_weather(tmp_value)
                elif tmp_key == "Vegas Line":
                    (team_code, line) = convert_vegas_line(tmp_value)
                    self.json["betting"]["winner"] = team_code
                    self.json["betting"]["spread"] = line
                elif tmp_key == "Over/Under":
                    self.json["betting"]["over under"] = convert_overunder(tmp_value)

    def __parse_starter(self):
        """ Parse the list of starter and their positions. """
        soup = self.soups["starters"]
        # We get all the elements the match data-stat="pos", which is the table
        # element that has the words "Pos", which is unique to these tables.
        # Once we have these elements, we find their parents to get the whole
        # table.
        ths = soup.find_all("th", attrs={"data-stat": "pos"})
        for th in ths:
            table = th.parent.parent  # th.parent == row, row.parent == table
            for row in table.find_all("tr"):
                # We read through the rows in order. Since the header with the
                # name always comes before the players for a team, we can set
                # the dictionary at the first time we hit it and it will be
                # good for the rest of the table.

                # Header row with team name
                if "stat_total" in row["class"]:
                    team_name = row.get_text(' ', strip=True)
                    team_code = names_to_code[team_name]
                    # Set the working dictionary based on the team
                    if team_code == self.home_team:
                        p_dict = self.json["players"]["home"]
                        p_set = self.home_players
                    else:
                        p_dict = self.json["players"]["away"]
                        p_set = self.away_players
                # Normal rows have blank classes
                elif row["class"] == ['']:
                    cols = row.find_all("td")
                    player = cols[0].get_text(' ', strip=True).replace('\n', ' ')
                    position = cols[1].get_text(' ', strip=True).replace('\n', ' ')
                    # We try to add the player to the list, but if the list
                    # doesn't exist, we have to make it first
                    try:
                        p_dict[position].append(player)
                    except KeyError:
                        p_dict[position] = [player]
                    # We also add to our internal set used to get teams from
                    # players in playbyplay
                    p_set.add(player)

    def __get_all_players(self):
        """ Get all player names from the various tables and store them in the
        player sets. """
        l_soups = [self.soups["def_stats"]]
        l_soups.append(self.soups["off_stats"])
        l_soups.append(self.soups["kick_stats"])

        # Each soup is essentially the same, and we only care about the first
        # two columns
        for soup in l_soups:
            body = soup.find_all("tbody")
            for row in body[0].find_all("tr"):
                # The rows with players have blank classes
                if row["class"] == ['']:
                    cols = row.find_all("td")
                    player = cols[0].get_text(' ', strip=True).replace('\n', ' ')
                    team_code = cols[1].get_text(' ', strip=True).replace('\n', ' ')
                    # Assign by team code
                    if team_code == self.home_team:
                        self.home_players.add(player)
                    elif team_code == self.away_team:
                        self.away_players.add(player)

    def print_soups(self):
        """ Print out all the soups. """
        for key in self.soups:
            print("=====", key, "=====")
            print(self.soups[key].prettify())

    def __repr__(self):
        """ Method that returns a representation of the contents. """
        return self.json.__repr__()

    def __str__(self):
        """ Method that returns a string of the contents for printing. """
        return self.json.__str__()


if __name__ == '__main__':
    # We only need to parse commandline flags if running as the main script
    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument('file', type=str, nargs="+",
            help="a raw data file to convert to JSON")
    args = argparser.parse_args()

    for raw_file in args.file:
        converter = Converter(raw_file)
        #print(converter)
        print(json.dumps(converter.json, sort_keys=True, indent=2, separators=(',', ': ')))

        #converter.print_soups()
