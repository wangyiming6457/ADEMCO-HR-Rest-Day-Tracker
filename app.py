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
    
    # Updated to require In Time and Out Time columns
    required_cols = ['Name', 'Date', 'In Time', 'Out Time']
    if not all(col in df.columns for col in required_cols):
        st.error(f"❌ Error: Could not find all required columns ({', '.join(required_cols)}). Please check your file.")
        return pd.DataFrame()

    # Keep only the columns we need
    df = df[required_cols].copy()
    
    # Drop rows where Name or Date is missing
    df = df.dropna(subset=['Name', 'Date'])
    
    # Standardize formats
    df['Name'] = df['Name'].astype(str).str.strip().str.upper()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.normalize()
    
    # Drop rows with invalid dates
    df = df.dropna(subset=['Date'])
    
    # Identify the absolute latest date in the entire uploaded dataset for our cutoff rule
    max_dataset_date = df['Date'].max()

    # Drop duplicate shift days and sort chronologically
    df = df.drop_duplicates(subset=['Name', 'Date'])
    df = df.sort_values(by=['Name', 'Date'])

    # The Streak Algorithm
    df['Date_Diff'] = df.groupby('Name')['Date'].diff().dt.days
    df['New_Streak'] = df['Date_Diff'] != 1
    df['Streak_ID'] = df.groupby('Name')['New_Streak'].cumsum()

    # Summarize the streaks (Now pulling exact In/Out times)
    summary = df.groupby(['Name', 'Streak_ID']).agg(
        Consecutive_Days=('Date', 'count'),
        Last_Shift_Date=('Date', 'max'),       # Kept temporarily for the cutoff math
        Start_Time=('In Time', 'first'),       # The 'In Time' of the first shift in the streak
        End_Time=('Out Time', 'last')          # The 'Out Time' of the last shift in the streak
    ).reset_index()

    # Filter 1: Must be 7 or more consecutive days
    flagged = summary[summary['Consecutive_Days'] >= 7].copy()
    
    # Filter 2: The streak must end on the max date OR the day before (to catch night shifts!)
    if not flagged.empty:
        cutoff_date = max_dataset_date - pd.Timedelta(days=1)
        flagged = flagged[flagged['Last_Shift_Date'] >= cutoff_date]
    
    if not flagged.empty:
        def set_alert(days):
            if days > 12:
                return "🚨 MOM BREACH (>12 Days)"
            elif days >= 11:
                return "🔴 Critical (11-12 Days)"
            else:
                return "⚠️ Warning (7-10 Days)"
                
        flagged['Alert_Status'] = flagged['Consecutive_Days'].apply(set_alert)
        
        # Clean up the output table by dropping the background calculation columns
        flagged = flagged.drop(columns=['Streak_ID', 'Last_Shift_Date'])
        
        # Rename columns to look nice for HR
        flagged = flagged.rename(columns={
            'Start_Time': 'First Shift (In Time)',
            'End_Time': 'Last Shift (Out Time)'
        })
        
        # Sort by worst offenders first
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
