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

# --- AI SUMMARY (Gemini) ---
# Refactored to not rely on get_detailed_stats and to use the LLM to get data
def generate_ai_summary(selected_players):
    """
    Generates an AI summary by instructing the Gemini LLM to find and analyze player data.
    """
    if not selected_players:
        return "Please select at least one player to generate an analysis."
    
    player_names_str = ", ".join(selected_players)
    
    prompt = (
        "Act as a top-tier fantasy football analyst. My task is to provide a concise analysis of the following NFL players: "
        f"{player_names_str}. "
        "Your first step is to perform a Google Search to get the latest 2025 seasonal statistics for each of these players. "
        "Make sure to include stats like Receptions, ReceivingYards, ReceivingTouchdowns, RushingYards, and RushingTouchdowns. "
        "Once you have the data, provide a concise analysis of each player's fantasy football value for the remainder of the season. "
        "Your analysis must include: "
        "* A quick overview of each player's statistical performance based on the data you found. "
        "* A brief commentary on their potential fantasy football value (e.g., \"High-End WR1\", \"Mid-Range TE2\"). "
        "After the analysis, present all of the information in a single, comprehensive data table with the following columns in this exact order: "
        "Player Name, Team, Position, Receptions, ReceivingYards, ReceivingTouchdowns, RushingYards, RushingTouchdowns, FumblesLost, and OverallFantasyFootballValue. "
        "Sort the table by highest to lowest ReceivingYards. Ensure all data in the table is directly from the data you found. Do not add any new projections or statistics beyond what you are given."
    )
    
    try:
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
                    # FIX: Call the refactored function that doesn't rely on the API for stats
                    ai_summary = generate_ai_summary(selected_players)
                    
                    st.markdown("### Detailed Report")
                    st.markdown(ai_summary)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
