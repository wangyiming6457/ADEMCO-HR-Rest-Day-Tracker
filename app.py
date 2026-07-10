import streamlit as st
import pandas as pd
import io
from datetime import date, timedelta

# ==========================================
# CORE LOGIC (Updated with 1-Day Night Shift Buffer)
# ==========================================
def analyze_rest_days(df):
    """Processes the dataframe to find consecutive working days >= 7"""
    df.columns = df.columns.str.strip()
    
    if 'Name' not in df.columns or 'Date' not in df.columns:
        st.error("❌ Error: Could not find 'Name' or 'Date' columns. Please check your file.")
        return pd.DataFrame()

    df = df[['Name', 'Date']].copy()
    df = df.dropna(subset=['Name', 'Date'])
    df['Name'] = df['Name'].astype(str).str.strip().str.upper()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.normalize()
    df = df.dropna(subset=['Date'])
    
    # Identify the absolute latest date in the entire uploaded dataset
    max_dataset_date = df['Date'].max()

    df = df.drop_duplicates(subset=['Name', 'Date'])
    df = df.sort_values(by=['Name', 'Date'])

    df['Date_Diff'] = df.groupby('Name')['Date'].diff().dt.days
    df['New_Streak'] = df['Date_Diff'] != 1
    df['Streak_ID'] = df.groupby('Name')['New_Streak'].cumsum()

    summary = df.groupby(['Name', 'Streak_ID']).agg(
        Consecutive_Days=('Date', 'count'),
        Start_Date=('Date', 'min'),
        End_Date=('Date', 'max')
    ).reset_index()

    # Filter 1: Must be 7 or more consecutive days
    flagged = summary[summary['Consecutive_Days'] >= 7].copy()
    
    # Filter 2: The streak must end on the max date OR the day before (to catch night shifts!)
    if not flagged.empty:
        # We subtract 1 day from the max date to create our cutoff
        cutoff_date = max_dataset_date - pd.Timedelta(days=1)
        flagged = flagged[flagged['End_Date'] >= cutoff_date]
    
    if not flagged.empty:
        def set_alert(days):
            if days > 12:
                return "🚨 MOM BREACH (>12 Days)"
            elif days >= 11:
                return "🔴 Critical (11-12 Days)"
            else:
                return "⚠️ Warning (7-10 Days)"
                
        flagged['Alert_Status'] = flagged['Consecutive_Days'].apply(set_alert)
        flagged = flagged.drop(columns=['Streak_ID'])
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

# ADEMCO Branding and Header
st.markdown("### 🏢 ADEMCO | HR Operations")
st.title("Security Officer Rest Day Tracker")

# Privacy Note for Peace of Mind
st.caption("🔒 **Data Privacy:** This tool processes data strictly in-memory. No employee files or records are saved or stored. All data is wiped the moment you close this page.")

# Dynamic Date Calculation for HR Instructions
two_weeks_ago = date.today() - timedelta(days=14)
target_date_str = two_weeks_ago.strftime("%d %B %Y")

# Crucial Instructions for HR with dynamic date
st.info(f"💡 **Important Note:** To ensure the app does not miss out on workers who are already on a streak, please upload data starting from at least **{target_date_str}** (2 weeks before today).")

st.markdown("---")

# File Uploader
uploaded_file = st.file_uploader("Upload Attendance Export (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    with st.spinner("Analyzing personnel shifts..."):
        try:
            # Read file based on extension
            if uploaded_file.name.endswith('.csv'):
                raw_data = pd.read_csv(uploaded_file)
            else:
                raw_data = pd.read_excel(uploaded_file)
                
            # Run the analysis
            results = analyze_rest_days(raw_data)
            
            if not results.empty:
                st.subheader("Action Required: Flagged Personnel")
                st.markdown("Officers highlighted in **red** have exceeded the legal 12-day limit. *(Note: Officers who are already on a rest day are excluded from this list).*")
                
                # Apply the highlight styling to the dataframe
                styled_results = results.style.apply(highlight_breaches, axis=1)
                
                # Display the Table
                st.dataframe(styled_results, use_container_width=True, hide_index=True)
                
                # Export Feature
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
