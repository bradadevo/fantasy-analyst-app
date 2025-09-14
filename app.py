import streamlit as st
import os
import json
import requests
import google.generativeai as genai

# --- Load API Keys from Streamlit Secrets ---
try:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    SPORTS_DATA_API_KEY = st.secrets['SPORTS_DATA_API_KEY']
except KeyError:
    st.error("API keys not found. Please add them to your Streamlit secrets.")
    st.stop()

# --- Function to Get All Players from SportsData.io ---
@st.cache_data(ttl=86400) # Caches the player list for 24 hours
def get_all_players_data():
    """Fetches a complete list of all NFL players from SportsData.io."""
    try:
        url = "https://api.sportsdata.io/v3/nfl/scores/json/Players"
        headers = {
            'Ocp-Apim-Subscription-Key': SPORTS_DATA_API_KEY,
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raises an HTTPError for bad status codes
        
        return response.json()
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            st.error(f"HTTP Error: Status Code {e.response.status_code} - URL: {e.request.url}")
        else:
            st.error(f"Network Error: {e}")
        return []

# --- Function to Get Player List for Multiselect ---
def get_player_list_options(all_players):
    """Filters the full player data for WRs and TEs to populate the multiselect."""
    wr_te_players = [
        f'{player.get("Name")} ({player.get("Team")})'
        for player in all_players
        if player.get("Position") in ["WR", "TE"] and player.get("Status") == "Active"
    ]
    wr_te_players.sort()
    return wr_te_players


# --- Function to Get Detailed Player Stats for AI Prompt ---
def get_player_stats(selected_players, all_players):
    """Filters the all_players data to get detailed stats for selected players."""
    player_stats_data = {}
    
    # Create a lookup dictionary for efficient searching
    player_lookup = {f'{p.get("Name")} ({p.get("Team")})': p for p in all_players}
    
    for player_full_name in selected_players:
        stats = player_lookup.get(player_full_name)
        if stats:
            player_stats_data[player_full_name] = stats
        
    return player_stats_data


# --- Page Setup and Title ---
st.set_page_config(page_title="Fantasy Football Analyst", layout="wide")
st.title("🏈 Fantasy Football Player Analyst")
st.write("Get a data-driven report on players for the rest of the season.")

# Fetch all players once and cache the result
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
                    # Fix: The `get_player_stats` function is now called here to define `detailed_stats`.
                    detailed_stats = get_player_stats(selected_players, all_players_data)

                    if not detailed_stats:
                        st.error("No statistics were found for the selected players. The API may not have data for them yet.")
                        st.stop()

                    prompt_text = (
                        "Act as a top-tier fantasy football analyst. I have compiled the following up-to-date player data for the current NFL season: "
                        "Player data: {provided_player_data}. "
                        "Using this data, provide a concise analysis of each player's fantasy football value for the remainder of the season. Focus on their current production and how it compares to other players at their position based on the provided statistics. "
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
