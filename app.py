import streamlit as st
import requests
import pandas as pd
import time

def calculate_threat_score(personalstats, profile_data=None):
    """Calculate the threat score based on user stats."""
    xanaxtaken = personalstats.get('xanaxtaken', 0)
    refills = personalstats.get('refills', 0)
    energydrinkused = personalstats.get('energydrinkused', 0)
    statenhancersused = personalstats.get('statenhancersused', 0)
    attackswon = personalstats.get('attackswon', 0)
    networth = personalstats.get('networth', 0)
    
    # Active days is usually top level in profile, but fallback to personalstats if possible
    days_active = 0
    if profile_data and 'age' in profile_data:
         days_active = profile_data['age']
    
    base_score = (xanaxtaken * 250) + (refills * 150) + (energydrinkused * 25) + (statenhancersused * 100000)
    activity_score = (days_active * 10) + (attackswon * 5)
    wealth_score = (networth / 1000000)
    
    return base_score + activity_score + wealth_score

def get_verdict(ratio):
    """Determine the verdict based on power ratio."""
    if ratio < 0.5:
        return "Green Light"
    elif ratio <= 1.2:
        return "Yellow Light"
    else:
        return "Red Light"

def main():
    # Keep layout="wide" but Streamlit natively handles mobile stacking
    st.set_page_config(page_title="Threat Assessment", page_icon="⚔️", layout="centered")
    
    st.title("Torn City Threat Assessment")
    st.write("Generate a personalized Threat Assessment dashboard against an enemy faction.")
    
    # Move inputs out of the sidebar and into an expander or container for better mobile UX
    with st.container():
        st.subheader("Configuration")
        
        # Added helper text for API Key
        api_key = st.text_input(
            "Enter Your Public API Key", 
            type="password",
            help="You can find your 'Public API Key' in Torn by going to your Preferences (the gear icon) -> API Settings. Create a new key with 'Public' access level."
        )
        
        # Added helper text for Faction ID
        faction_id = st.text_input(
            "Enter Enemy Faction ID",
            help="To find a Faction ID, go to their faction page in Torn and look at the URL. It will be the number at the end: e.g., torn.com/factions.php?step=profile&ID=12345 (The ID is 12345)."
        )
        
        submit_btn = st.button("Generate Hitlist", type="primary", use_container_width=True)

    st.divider()

    if submit_btn:
        if not api_key or not faction_id:
            st.error("Please enter both your API Key and the Enemy Faction ID.")
            return
            
        # First API call - fetch User's own data
        with st.spinner("Fetching User Data..."):
            user_url = f"https://api.torn.com/user/?selections=personalstats,profile&key={api_key}"
            response = requests.get(user_url)
            
            if response.status_code != 200:
                st.error("Failed to connect to Torn API.")
                return
                
            user_data = response.json()
            if 'error' in user_data:
                st.error(f"Error fetching user data: {user_data['error'].get('error', 'Unknown error')}")
                return
            
            user_name = user_data.get('name', 'User')
            user_stats = user_data.get('personalstats', {})
            user_threat_score = calculate_threat_score(user_stats, user_data)
            
            st.success(f"**Your Threat Score** ({user_name}): {user_threat_score:,.0f}")
        
        # Second API call - fetch Enemy Faction's members
        with st.spinner("Fetching Enemy Faction Data..."):
            time.sleep(0.65)  # Enforce 100 calls/min limit
            faction_url = f"https://api.torn.com/faction/{faction_id}?selections=basic&key={api_key}"
            fac_response = requests.get(faction_url)
            
            if fac_response.status_code != 200:
                st.error("Failed to connect to Torn API when fetching faction.")
                return
                
            fac_data = fac_response.json()
            if 'error' in fac_data:
                st.error(f"Error fetching faction data: {fac_data['error'].get('error', 'Unknown error')}")
                return
            
            members = fac_data.get('members', {})
            if not members:
                st.warning("No members found in this faction.")
                return
                
            total_members = len(members)
            st.info(f"Found {total_members} members in the enemy faction. Generating Hitlist...")
            
            progress_bar = st.progress(0, text="Analyzing enemy members...")
            
            enemy_results = []
            
            # Loop API calls for each faction member
            for idx, (member_id, member_info) in enumerate(members.items()):
                time.sleep(0.65)  # Strict constraint: sleep inside loop after every call
                
                member_url = f"https://api.torn.com/user/{member_id}?selections=personalstats,profile&key={api_key}"
                mem_resp = requests.get(member_url)
                
                if mem_resp.status_code == 200:
                    mem_data = mem_resp.json()
                    
                    if 'error' not in mem_data:
                        mem_name = mem_data.get('name', f'Unknown[{member_id}]')
                        mem_stats = mem_data.get('personalstats', {})
                        
                        mem_threat_score = calculate_threat_score(mem_stats, mem_data)
                        
                        # Handle division by zero scenario if user threat score is 0
                        if user_threat_score > 0:
                            power_ratio = mem_threat_score / user_threat_score
                        else:
                            power_ratio = float('inf') if mem_threat_score > 0 else 0.0
                            
                        verdict = get_verdict(power_ratio)
                        
                        enemy_results.append({
                            'ID': member_id,
                            'Name': mem_name,
                            'Threat Score': mem_threat_score,
                            'Power Ratio': round(power_ratio, 3),
                            'Verdict': verdict
                        })
                
                # Update progress
                progress_bar.progress((idx + 1) / total_members, text=f"Analyzing member {idx + 1}/{total_members}")
            
            # Final output rendering
            progress_bar.empty()
            
            if enemy_results:
                st.subheader("Hitlist Assessment")
                df = pd.DataFrame(enemy_results)
                
                # Optionally style the dataframe for verdicts
                def highlight_verdict(val):
                    if val == 'Green Light':
                        return 'color: #00ff00;' # Custom terminal-like green
                    elif val == 'Yellow Light':
                        return 'color: #ffcc00;'
                    elif val == 'Red Light':
                        return 'color: #ff4444;'
                    return ''
                    
                styled_df = df.style.map(highlight_verdict, subset=['Verdict']).format({'Threat Score': '{:,.0f}'})
                
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                st.error("Could not compute threat scores for any faction members.")

if __name__ == "__main__":
    main()
