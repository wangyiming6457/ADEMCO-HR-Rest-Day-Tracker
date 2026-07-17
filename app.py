import streamlit as st
import pandas as pd
import io
from datetime import date, timedelta

# ==========================================
# CORE LOGIC 
# ==========================================
def analyze_rest_days(df):
    """Processes the dataframe to find consecutive working days >= 7"""
    df.columns = df.columns.str.strip()
    
    required_cols = ['Name', 'Date', 'In Time', 'Out Time']
    if not all(col in df.columns for col in required_cols):
        st.error(f"❌ Error: Could not find all required columns ({', '.join(required_cols)}). Please check your file.")
        return pd.DataFrame()

    df = df[required_cols].copy()
    df = df.dropna(subset=['Name', 'Date', 'In Time', 'Out Time'])
    
    # Standardize formats
    df['Name'] = df['Name'].astype(str).str.strip().str.upper()
    
    # FIX: Added dayfirst=True to handle DD-MM-YYYY formats properly!
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.normalize()
    
    t_in = pd.to_datetime(df['In Time'], errors='coerce', dayfirst=True)
    t_out = pd.to_datetime(df['Out Time'], errors='coerce', dayfirst=True)
    
    # Extract the exact calendar date they physically left the site
    df['Out_Date'] = t_out.dt.normalize()
    
    df = df.dropna(subset=['Date', 'Out_Date'])
    
    # Clean out accidental short taps (< 15 mins)
    shift_duration_minutes = (t_out - t_in).dt.total_seconds() / 60.0
    df = df[shift_duration_minutes >= 15].copy()
    
    # Identify the absolute latest physical date anyone worked in the entire dataset (now safely includes the 17th!)
    max_physical_date = df['Out_Date'].max()

    df = df.drop_duplicates(subset=['Name', 'Date'])
    df = df.sort_values(by=['Name', 'Date'])

    # The Streak Algorithm
    df['Date_Diff'] = df.groupby('Name')['Date'].diff().dt.days
    df['New_Streak'] = df['Date_Diff'] != 1
    df['Streak_ID'] = df.groupby('Name')['New_Streak'].cumsum()

    # Summarize the streaks
    summary = df.groupby(['Name', 'Streak_ID']).agg(
        Consecutive_Days=('Date', 'count'),
        Last_Physical_Date=('Out_Date', 'last'), 
        Start_Time=('In Time', 'first'),
        End_Time=('Out Time', 'last')
    ).reset_index()

    # Filter 1: Must be 7 or more consecutive days
    flagged = summary[summary['Consecutive_Days'] >= 7].copy()
    
    # Filter 2: The guard must have physically worked/clocked out on the final day of the report
    if not flagged.empty:
        flagged = flagged[flagged['Last_Physical_Date'] == max_physical_date]
    
    if not flagged.empty:
        def set_alert(days):
            if days > 12:
                return "🚨 MOM BREACH (>12 Days)"
            elif days >= 11:
                return "🔴 Critical (11-12 Days)"
            else:
                return "⚠️ Warning (7-10 Days)"
                
        flagged['Alert_Status'] = flagged['Consecutive_Days'].apply(set_alert)
        flagged = flagged.drop(columns=['Streak_ID', 'Last_Physical_Date'])
        
        flagged = flagged.rename(columns={
            'Start_Time': 'First Shift (In Time)',
            'End_Time': 'Last Shift (Out Time)'
        })
        
        flagged = flagged.sort_values(by='Consecutive_Days', ascending=False)
        
    return flagged

# ==========================================
# UI STYLING FUNCTION
# ==========================================
def highlight_breaches(row):
    """Highlights the entire row in red if the guard worked more than 12 days"""
    if row['Consecutive_Days'] > 12:
        return ['background-color: #ffe6e6; color: #a30000; font-weight: bold'] * len(row)
    return [''] * len(row)

# ==========================================
# STREAMLIT UI
# ==========================================
st.set_page_config(page_title="ADEMCO HR Rest Day Tracker", page_icon="🏢", layout="wide")

st.markdown("### 🏢 ADEMCO | HR Operations")
st.title("Security Officer Rest Day Tracker")

st.caption("🔒 **Data Privacy:** This tool processes data strictly in-memory. No employee files or records are saved or stored. All data is wiped the moment you close this page.")

two_weeks_ago = date.today() - timedelta(days=14)
target_date_str = two_weeks_ago.strftime("%d %B %Y")

st.info(f"💡 **Important Note:** To ensure the app does not miss out on workers who are already on a streak, please upload data starting from at least **{target_date_str}** (2 weeks before today).")

st.markdown("---")

uploaded_file = st.file_uploader("Upload Attendance Export (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    with st.spinner("Analyzing personnel shifts..."):
        try:
            if uploaded_file.name.endswith('.csv'):
                raw_data = pd.read_csv(uploaded_file)
            else:
                raw_data = pd.read_excel(uploaded_file)
                
            results = analyze_rest_days(raw_data)
            
            if not results.empty:
                st.subheader("Action Required: Flagged Personnel")
                st.markdown("Officers highlighted in **red** have exceeded the legal 12-day limit. *(Note: Officers who have already finished their shifts yesterday and are currently resting are excluded).*")
                
                styled_results = results.style.apply(highlight_breaches, axis=1)
                st.dataframe(styled_results, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                csv_buffer = io.StringIO()
                results.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    label="📥 Download Action List (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name="ADEMCO_Rest_Day_Alerts.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.success("✅ **All Clear!** No security officers have an active streak of 7 or more consecutive days in this dataset.")
                
        except Exception as e:
            st.error(f"An error occurred while analyzing the file: {e}")
