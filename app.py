import streamlit as st
import os
import json
import requests
import google.generativeai as genai
from datetime import datetime

# --- Load API Keys from Streamlit Secrets ---
try:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    SPORTS_DATA_API_KEY = st.secrets['SPORTS_DATA_API_KEY']
except KeyError:
    st.error("API keys not found. Please add them to your Streamlit secrets.")
    st.stop()


# --- Function to Get All Players from SportsData.io ---
@st.cache_data(ttl=86400) # Caches the player list for 24 hours
def get_player_list():
    try:
        url = "https://api.sportsdata.io/v3/nfl/scores/json/Players"
        
        headers = {
            'Ocp-Apim-Subscription-Key': SPORTS_DATA_API_KEY,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        player_data = response.json()
        
        wr_te_players = [
            f'{player.get("Name")} ({player.get("Team")})'
            for player in player_data
            if player.get("Position") in ["WR", "TE"] and player.get("Status") == "Active"
        ]
        
        wr_te_players.sort()
        
        return wr_te_players
        
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            st.error(f"HTTP Error: Status Code {e.response.status_code} - URL: {e.request.url}")
        else:
            st.error(f"Network Error: {e}")
        return []

# --- New Function to Get Detailed Player Stats ---
@st.cache_data(ttl=3600) # Caches stats for 1 hour to prevent excessive API calls
def get_player_stats(player_names):
    if not player_names:
        return {}

    # Get the current NFL season year
    current_year = datetime.now().year
    
    player_stats_data = {}
    
    try:
        # We will use the PlayerSeasonStats endpoint for detailed stats
        url = f"https://api.sportsdata.io/v3/nfl/stats/json/PlayerSeasonStats/{current_year}"
        headers = {
            'Ocp-Apim-Subscription-Key': SPORTS_DATA_API_KEY,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        all_stats_data = response.json()
        
        for player_name in player_names:
            # The player name in the dropdown is "Name (Team)". Get just the name.
            name_only = player_name.split(' (')[0]
            
            # Find the player's stats from the full data list
            stats = next((p for p in all_stats_data if p.get('Name') == name_only), None)
            
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
PLAYER_OPTIONS = get_player_list()

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
            # --- Run the analysis with a loading spinner ---
            with st.spinner("Analyzing players and generating your report..."):
                try:
                    # --- Get the detailed stats for selected players ---
                    detailed_stats = get_player_stats(selected_players)

                    # --- NEW DIAGNOSTIC CODE ---
                    st.write("Data returned to the prompt:", detailed_stats)
                    # --- END OF NEW CODE ---
                    
                    # --- Construct the Detailed Gemini Prompt with REAL Data ---
                    prompt_text = (
                        "Act as a top-tier fantasy football analyst. I need a deep, data-driven analysis of a specific group of "
                        "either tight ends or wide receivers for the remainder of the season. Your analysis must be based on the "
                        "provided, up-to-date data. You are a subject matter expert and can use your training to find nuanced insights, "
                        "but you must prioritize the provided data for all player context and projections. "
                        "Here are the player names to analyze: " + ", ".join(selected_players) + "."
                        "For each player, provide a qualitative, in-depth analysis that simulates their possible production and "
                        "highlights their potential fantasy football value. Confirm the context of who they are and make sure they "
                        "are on the right team based on most recent and reliable data sources."
                        "Evaluate each player based on the following criteria: "
                        "* Their team's overall offensive scheme and how it caters to their position. "
                        "* The team's quarterback situation and potential for consistent production (scale of 1-10)."
                        "* The player's role in the red zone and their touchdown-scoring potential."
                        "* Their usage as a blocker versus a receiver. "
                        "* The percentage of time their team will likely play from behind, and how this impacts their target volume. "
                        "Consider likely weather and facility factors."
                        "Finally, present all of the information in a single, comprehensive data table with the following columns "
                        "in this exact order: "
                        "Player Name, Team, Bye Week, Projected Catches, Projected Yards, Projected Touchdowns, % Time Behind, "
                        "Upside (1-10), % First Read Target Share (Season Projection), Likely Snap Count Percentage, "
                        "Overall Fantasy Football Value, Fantasy Points, Targets per route run, Teams Offensive Plays/Count per game, "
                        "Yards per route run, Red Zone Target share. "
                        "Sort the final table by highest possible fantasy points using a half-PPR scoring format "
                        "(.5 points per reception, 6 points per TD, and 1 point per 10 yards)."
                        "Definition Details: "
                        "Always list the table column definitions out as the last text below the article. For all definitions except "
                        "Player Name, Team, Bye Week, explain the details of what a high, med, and low measurement should be to move a "
                        "player from a low, med, high end player in their position for measurement definition."
                        "Please provide a detailed analysis. Ensure all data points are meticulously vetted, cross-referenced with "
                        "multiple reputable sources, and validated for accuracy. The predictive models must be clearly explained, "
                        "detailing their underlying assumptions, limitations, and the specific metrics used for performance assessment. "
                        "The final output must be logically coherent and provide a deep assessment of the given scenario, "
                        "accounting for all relevant variables."
                        f"\n\nHere is the raw, factual data for the analysis: {json.dumps(detailed_stats)}"
                    )
                    
                    # Call the Gemini API
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt_text)
                    
                    # Display the final report
                    st.markdown("### Detailed Report")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
