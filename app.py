import streamlit as st
import os
import json
import requests
import google.generativeai as genai
from datetime import datetime

# --- Load API Keys from Streamlit Secrets ---
try:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    API_SPORTS_KEY = st.secrets['API_SPORTS_KEY']
except KeyError:
    st.error("API keys not found. Please add them to your Streamlit secrets.")
    st.stop()

API_BASE_URL = "https://v1.american-football.api-sports.io"
NFL_LEAGUE_ID = 1

# --- Function to Get Detailed Player Stats ---
@st.cache_data(ttl=3600)  # Caches stats for 1 hour
def get_player_stats(player_name):
    """
    Fetches detailed statistics for a single player using the API's search endpoint.
    """
    if not player_name:
        return None

    current_year = datetime.now().year
    headers = {'x-apisports-key': API_SPORTS_KEY}

    try:
        # Step 1: Search for the player to get their ID
        search_url = f"{API_BASE_URL}/players?league={NFL_LEAGUE_ID}&season={current_year}&search={player_name}"
        search_response = requests.get(search_url, headers=headers)
        search_response.raise_for_status()
        search_results = search_response.json().get('response', [])

        player_id = None
        if search_results:
            # Assuming the first result is the correct player
            player_id = search_results[0].get('id')

        if not player_id:
            return {"error": f"No player ID found for '{player_name}'. They may not be in the database for the current season."}

        # Step 2: Use the player ID to get detailed statistics
        stats_url = f"{API_BASE_URL}/players/statistics?id={player_id}&season={current_year}"
        stats_response = requests.get(stats_url, headers=headers)
        stats_response.raise_for_status()
        stats_result = stats_response.json().get('response', [])

        if not stats_result:
            return {"error": f"No statistics found for '{player_name}'. API may not have data for this player."}

        # Return a dictionary with the player's name as the key
        return {player_name: stats_result[0]}

    except requests.exceptions.RequestException as e:
        return {"error": f"An API request error occurred: {e}"}

# --- Page Setup and Title ---
st.set_page_config(page_title="Fantasy Football Analyst", layout="wide")
st.title("🏈 Fantasy Football Player Analyst")
st.write("Get a data-driven report on players for the rest of the season.")

# --- User Input Section ---
st.markdown("### Search for a Player to Analyze")

# Change from st.multiselect to st.text_input
player_input = st.text_input(
    "Enter a wide receiver or tight end's full name:",
    placeholder="e.g., DK Metcalf"
)

# --- Button to Trigger Analysis ---
if st.button("Generate Report", use_container_width=True):
    if not player_input:
        st.warning("Please enter a player's name to generate a report.")
    else:
        with st.spinner(f"Analyzing {player_input} and generating your report..."):
            try:
                detailed_stats = get_player_stats(player_input)

                if "error" in detailed_stats:
                    st.error(detailed_stats["error"])
                    st.stop()

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
