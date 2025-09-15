import streamlit as st
import os
import json
import requests
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# --- SETUP GEMINI WITH STREAMLIT SECRETS ---
try:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    SPORTS_DATA_API_KEY = st.secrets['SPORTS_DATA_API_KEY']
except KeyError:
    st.error("API keys not found. Please add them to your Streamlit secrets.")
    st.stop()

# --- DATA FETCHING FROM SPORTSDATA.IO ---
@st.cache_data(ttl=86400)
def get_all_players_data():
    """Fetches a complete list of all NFL players from SportsData.io."""
    try:
        url = "https://api.sportsdata.io/v3/nfl/scores/json/Players"
        headers = {
            'Ocp-Apim-Subscription-Key': SPORTS_DATA_API_KEY,
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            st.error(f"HTTP Error: Status Code {e.response.status_code} - URL: {e.request.url}")
        else:
            st.error(f"Network Error: {e}")
        return []

def get_player_list_options(all_players):
    """Filters the full player data for WRs and TEs to populate the multiselect."""
    wr_te_players = [
        f'{player.get("Name")} ({player.get("Team")})'
        for player in all_players
        if player.get("Position") in ["WR", "TE"] and player.get("Status") == "Active"
    ]
    wr_te_players.sort()
    return wr_te_players

def get_detailed_stats(player_ids):
    """
    Fetches detailed statistics for selected players by making a new API call
    for each player's stats.
    """
    detailed_stats_list = []
    
    current_season_year = datetime.now().year

    for player_id in player_ids:
        try:
            url = f"https://api.sportsdata.io/v3/nfl/scores/json/PlayerSeasonStatsByPlayerID/{current_season_year}/{player_id}"
            headers = {
                'Ocp-Apim-Subscription-Key': SPORTS_DATA_API_KEY,
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            player_stats = response.json()

            if player_stats and isinstance(player_stats, dict):
                detailed_stats_list.append(player_stats)
            else:
                st.warning(f"No detailed stats found for PlayerID: {player_id}.")
        except requests.exceptions.RequestException as e:
            st.warning(f"Could not retrieve data for a player with ID {player_id}. Error: {e}")
            continue
            
    return detailed_stats_list


# --- AI SUMMARY (Gemini) ---
def generate_ai_summary(player_stats_dict):
    """Generates an AI summary comparing player stats."""
    prompt = "You are an expert fantasy football analyst. Compare these players using the tables below:\n\n"
    
    valid_players = {player: df for player, df in player_stats_dict.items() if df is not None}
    
    if not valid_players:
        return "No player data was found to generate an AI summary."
        
    for player, stats in valid_players.items():
        df = pd.DataFrame([stats])
        prompt += f"\n### {player}\n{df.to_string(index=False)}\n"

    prompt += "\nGive a clear summary of who has the best outlook this week and why. Keep it concise but insightful."

    try:
        # UPDATED: Using the gemini-2.5-flash model
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while generating the AI summary: {e}"

# --- STREAMLIT APP LAYOUT ---
st.set_page_config(page_title="Fantasy Football Analyst", layout="wide")
st.title("🏈 Fantasy Football Player Analyst")
st.write("Using SportsData.io data with **AI-powered reasoning** by Gemini.")

all_players_data = get_all_players_data()

if not all_players_data:
    st.warning("Could not load the full player list from SportsData.io. Please check your API key and try again.")
    st.stop()
else:
    PLAYER_OPTIONS = get_player_list_options(all_players_data)
    
    selected_players = st.multiselect(
        "Choose one or more wide receivers or tight ends:",
        options=PLAYER_OPTIONS,
        placeholder="Select players..."
    )

    if st.button("Generate Report", use_container_width=True):
        if not selected_players:
            st.warning("Please select at least one player to generate a report.")
        else:
            with st.spinner("Analyzing players and generating your report..."):
                try:
                    player_id_map = {f'{p.get("Name")} ({p.get("Team")})': p.get("PlayerID") for p in all_players_data}
                    selected_player_ids = [player_id_map[name] for name in selected_players]

                    detailed_stats_list = get_detailed_stats(selected_player_ids)
                    
                    if not detailed_stats_list:
                        st.error("No statistics were found for the selected players. The API may not have data for them yet.")
                        st.stop()
                    
                    detailed_stats = {f'{p.get("Name")} ({p.get("Team")})': p for p in detailed_stats_list}

                    ai_summary = generate_ai_summary(detailed_stats)
                    
                    st.markdown("### Detailed Report")
                    st.markdown(ai_summary)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
