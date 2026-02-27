import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Page Config
st.set_page_config(page_title="Railway Speed Analyzer", layout="centered")

# UI Styling Fix
st.markdown("""
    <style>
    .main { background-color: #FFF5E6; }
    .stButton>button { background-color: #FF9933; color: white; border-radius: 8px; width: 100%; }
    </style>
    """, unsafe_allow_html=True) # Corrected parameter name

st.title("🚉 Railway Speed Profile")
st.write("Professional Sequence Analyzer (Mobile Ready)")

# Sidebar for Files
st.sidebar.header("📁 Upload Data")
rtis_f = st.sidebar.file_uploader("1. RTIS Data", type=['csv', 'xlsx'])
dlog_f = st.sidebar.file_uploader("2. Datalogger Data", type=['csv', 'xlsx'])
sig_f = st.sidebar.file_uploader("3. Signal Mapping", type=['csv', 'xlsx'])

def clean_id(s):
    m = re.search(r'([AS])?-?(\d+)', str(s).upper())
    return f"{m.group(1) or 'S'}{m.group(2)}" if m else None

if rtis_f and dlog_f and sig_f:
    def read_df(f):
        if f.name.endswith('.csv'): return pd.read_csv(f, encoding='latin1', on_bad_lines='skip')
        return pd.read_excel(f)

    sig_m = read_df(sig_f)
    up_sigs = {clean_id(s) for s in sig_m.iloc[:, 6].dropna().astype(str) if clean_id(s)}

    rtis = read_df(rtis_f)
    rtis.columns = rtis.columns.str.strip()
    rtis['Logging Time'] = pd.to_datetime(rtis['Logging Time'], errors='coerce')
    rtis = rtis.dropna(subset=['Logging Time']).sort_values('Logging Time')
    rtis['CumDist'] = pd.to_numeric(rtis['distFromSpeed'], errors='coerce').fillna(0).cumsum()
    rtis['STN_KEY'] = rtis['STATION NAME'].astype(str).str.upper().str.strip()

    dlog = read_df(dlog_f)
    dlog.columns = dlog.columns.str.strip()
    dlog['dt'] = pd.to_datetime(dlog['SIGNAL TIME'].astype(str).str.replace(r':(\d{3})$', r'.\1', regex=True), 
                                format='%d/%m/%Y %H:%M:%S.%f', errors='coerce')
    dlog = dlog.dropna(subset=['dt']).sort_values('dt')

    events, aspect_mem = [], {}
    RECR_ON = ['CLOSED', 'UP', 'PICKUP', 'OCCURRED', 'ON']
    
    for _, row in dlog.iterrows():
        sig_full = str(row['SIGNAL NAME']).strip().upper()
        base_sig, status = clean_id(sig_full), str(row['SIGNAL STATUS']).strip().upper()
        stn = str(row['STATION NAME']).split('-')[0].upper().strip()

        if base_sig in up_sigs:
            key = (stn, base_sig)
            if any(x in status for x in ['DOWN', 'OPENED', 'DROP', 'OFF']):
                if 'HHECP' in sig_full or 'HHECR' in sig_full: aspect_mem[key] = "Double Yellow"
                elif 'HECP' in sig_full or 'HECR' in sig_full: aspect_mem[key] = "Single Yellow"
                elif 'DECR' in sig_full: aspect_mem[key] = "Green"

            if 'RECR' in sig_full and status in RECR_ON:
                ev_time = row['dt']
                t_diffs = (rtis['Logging Time'] - ev_time).abs()
                best_idx = t_diffs.idxmin()
                best_pt = rtis.loc[best_idx]
                
                if t_diffs[best_idx].total_seconds() <= 5 and best_pt['STN_KEY'] == stn:
                    if best_pt['Speed'] > 1:
                        events.append({
                            'Time': ev_time, 'Station': stn, 'Signal': base_sig,
                            'Aspect': aspect_mem.get(key, "Single Yellow"), 
                            'Speed': best_pt['Speed'], 'Dist': best_pt['CumDist']
                        })
                aspect_mem[key] = None

    if events:
        event_df = pd.DataFrame(events).sort_values('Time').drop_duplicates(subset=['Station', 'Signal'])
        st.write("---")
        idx = st.selectbox("📋 Choose Event:", options=range(len(event_df)),
                           format_func=lambda i: f"{i+1}. {event_df.iloc[i]['Station']} - {event_df.iloc[i]['Signal']}")
        sel = event_df.iloc[idx]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = {"Green": "#E6FFED", "Single Yellow": "#FFFDE6", "Double Yellow": "#FFF5E6"}
        ax.set_facecolor(colors.get(sel['Aspect'], "#FFFFFF"))
        
        subset = rtis[(rtis['CumDist'] >= sel['Dist'] - 1000) & (rtis['CumDist'] <= sel['Dist'] + 1000)]
        ax.plot(subset['Logging Time'], subset['Speed'], color='blue', lw=2)
        ax.axvline(x=sel['Time'], color='red', linestyle='--')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        st.pyplot(fig)
        
        st.success(f"Time: {sel['Time'].strftime('%H:%M:%S.%f')[:-3]} | Speed: {sel['Speed']} km/h")
    else:
        st.info("Upload files to start analysis.")