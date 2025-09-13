import streamlit as st
import os
import json
import requests
import google.generativeai as genai
from datetime import datetime

# --- Load API Keys from Streamlit Secrets ---
try:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    # The API-Sports key uses a different header name
    API_SPORTS_KEY = st.secrets['API_SPORTS_KEY']
except KeyError:
    st.error("API keys not found. Please add them to your Streamlit secrets.")
    st.stop()


# --- Function to Get NFL League ID ---
@st.cache_data(ttl=86400) # Caches the league ID for 24 hours
def get_nfl_league_id():
    try:
        url = "https://v1.american-football.api-sports.io/leagues"
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        leagues = response.json().get('response', [])
        
        # Find the NFL league ID
        nfl_league = next((l for l in leagues if l.get('name') == 'NFL'), None)
        return nfl_league.get('id') if nfl_league else None
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching league ID from API: {e}")
        return None

# --- Function to Get All Players from API-Sports ---
@st.cache_data(ttl=86400) # Caches the player list for 24 hours
def get_player_list(league_id):
    try:
        url = f"https://v1.american-football.api-sports.io/players?league={league_id}&season={datetime.now().year}"
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        player_data = response.json().get('response', [])
        
        wr_te_players = [
            f'{player.get("firstname")} {player.get("lastname")} ({player.get("team")})'
            for player in player_data
            if player.get("position") in ["WR", "TE"]
        ]
        
        wr_te_players.sort()
        
        return wr_te_players
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching player data from API: {e}")
        return []

# --- Function to Get Detailed Player Stats ---
@st.cache_data(ttl=3600) # Caches stats for 1 hour
def get_player_stats(player_names, league_id):
    if not player_names:
        return {}

    current_year = datetime.now().year
    player_stats_data = {}
    
    try:
        url = f"https://v1.american-football.api-sports.io/players/statistics?league={league_id}&season={current_year}"
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        all_stats_data = response.json().get('response', [])

        stats_by_name = {f'{p.get("firstname")} {p.get("lastname")}': p for p in all_stats_data}

        for player_name in player_names:
            name_only = player_name.split(' (')[0]
            stats = stats_by_name.get(name_only, None)

            if stats:
                player_stats_data[name_only] = stats
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching stats for players: {e}")
        return {}
    
    return player_stats_data


# --- Page Setup and Title ---
st.set_page_config(page_title="Fantasy Football Analyst", layout="wide")
st.title("🏈 Fantasy Football Player Analyst")
st.write("Get a data-driven report on players for the rest of the season.")


# --- User Input Section ---
st.markdown("### Select Players to Analyze")

nfl_league_id = get_nfl_league_id()

if nfl_league_id is None:
    st.error("Could not find NFL league. Please check your API key and try again.")
else:
    PLAYER_OPTIONS = get_player_list(nfl_league_id)
    
    if not PLAYER_OPTIONS:
        st.warning("Could not load the player list. Please check your API key and try again later.")
    else:
        selected_players = st.multiselect(
            "Choose one or more wide receivers or tight ends:",
            options=PLAYER_OPTIONS,
            placeholder="Select players..."
        )

        # --- Button to Trigger Analysis ---
        if st.button("Generate Report", use_container_width=True):
            if not selected_players:
                st.warning("Please select at least one player to generate a report.")
            else:
                with st.spinner("Analyzing players and generating your report..."):
                    try:
                        detailed_stats = get_player_stats(selected_players, nfl_league_id)
                        
                        prompt_text = (
                            "Act as a top-tier fantasy football analyst. I have compiled the following up-to-date player data for the current NFL season: "
                            "Player data: {provided_player_data}. "
                            "Using this data, provide a concise analysis of each player's fantasy football value for the remainder of the season. Focus on their current production and how it compares to other players at their position. "
                            "Your analysis must include: "
                            "* A quick overview of each player's statistical performance based on the provided data. "
                            "* A brief commentary on their potential fantasy football value (e.g., \"High-End WR1\", \"Mid-Range TE2\"). "
                            "After the analysis, present all of the information in a single, comprehensive data table with the following columns in this exact order: "
                            "Player Name, Team, Position, Receptions, ReceivingYards, ReceivingTouchdowns, RushingYards, RushingTouchdowns, FumblesLost, and OverallFantasyFootballValue. "
                            "Sort the table by highest to lowest ReceivingYards. Ensure all data in the table is directly from the provided JSON. Do not add any new projections or statistics beyond what you are given."
                            f"\n\nHere is the raw, factual data for the analysis: {json.dumps(detailed_stats)}"
                        )
                        
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(prompt_text)
                        
                        st.markdown("### Detailed Report")
                        st.markdown(response.text)

                    except Exception as e:
                        st.error(f"An error occurred: {e}")
