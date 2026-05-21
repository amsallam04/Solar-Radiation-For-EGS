import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from pvlib.solarposition import get_solarposition
import pytz
from datetime import datetime, time
import base64

# Constants
SOLAR_CONSTANT = 1367  # W/m^2

# Set page configuration
st.set_page_config(
    page_title="Solar Radiation Dashboard",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for solar theme
def add_solar_theme():
    st.markdown("""
    <style>
        /* Light solar theme colors */
        :root {
            --solar-yellow: #FFD700;
            --solar-orange: #FFA500;
            --solar-light-orange: #FFCC80;
            --solar-light-yellow: #FFF8E1;
            --solar-blue: #87CEEB;
            --solar-dark-blue: #4682B4;
            --solar-text: #333333;
            --solar-light-bg: #FFFAF0;
        }
        
        /* Main background */
        .stApp {
            background: linear-gradient(135deg, var(--solar-light-bg) 0%, #FFFCF5 100%);
        }
        
        /* Headers */
        h1, h2, h3 {
            color: var(--solar-orange) !important;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        
        /* Sidebar */
        .css-1d391kg, .css-12oz5g7 {
            background: linear-gradient(180deg, var(--solar-light-orange) 0%, var(--solar-orange) 100%);
        }
        
        .sidebar .sidebar-content {
            background: linear-gradient(180deg, var(--solar-light-orange) 0%, var(--solar-orange) 100%);
        }
        
        /* Buttons */
        .stButton>button {
            background: linear-gradient(90deg, var(--solar-yellow) 0%, var(--solar-orange) 100%);
            color: var(--solar-text);
            border: none;
            font-weight: bold;
            transition: all 0.3s;
            border-radius: 10px;
            padding: 0.5rem 1rem;
        }
        
        .stButton>button:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Input fields */
        .stNumberInput, .stTextInput, .stSlider, .stSelectbox {
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 0.5rem;
            margin-bottom: 1rem;
        }
        
        /* DataFrames */
        .dataframe {
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Download button */
        .stDownloadButton>button {
            background: linear-gradient(90deg, var(--solar-blue) 0%, var(--solar-dark-blue) 100%);
            color: white;
            border: none;
            font-weight: bold;
            transition: all 0.3s;
            border-radius: 10px;
            padding: 0.5rem 1rem;
        }
        
        .stDownloadButton>button:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Card-like containers */
        .solar-card {
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
            border-left: 5px solid var(--solar-orange);
        }
        
        /* Sun animation */
        @keyframes sun-glow {
            0% { box-shadow: 0 0 10px 5px rgba(255, 215, 0, 0.5); }
            50% { box-shadow: 0 0 20px 10px rgba(255, 215, 0, 0.7); }
            100% { box-shadow: 0 0 10px 5px rgba(255, 215, 0, 0.5); }
        }
        
        .sun-icon {
            display: inline-block;
            width: 50px;
            height: 50px;
            background-color: var(--solar-yellow);
            border-radius: 50%;
            animation: sun-glow 3s infinite;
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
        
        /* Top header with sun icon */
        .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            position: relative;
        }
        
        /* Info boxes */
        .info-box {
            background-color: var(--solar-light-yellow);
            border-radius: 10px;
            padding: 15px;
            border-left: 5px solid var(--solar-blue);
            margin-bottom: 20px;
        }
        
        /* Warning boxes */
        .warning-box {
            background-color: #FFF3E0;
            border-radius: 10px;
            padding: 15px;
            border-left: 5px solid #FF9800;
            margin-bottom: 20px;
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: white;
            border-radius: 10px 10px 0 0;
            padding: 10px 20px;
            border: none;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: var(--solar-light-orange);
            color: var(--solar-text);
            font-weight: bold;
        }
    </style>
    
    <!-- Sun icon in top right -->
    <div class="sun-icon"></div>
    """, unsafe_allow_html=True)

# Add solar theme
add_solar_theme()

# Function to create a card container
def card(title, content):
    st.markdown(f"""
    <div class="solar-card">
        <h3>{title}</h3>
        {content}
    </div>
    """, unsafe_allow_html=True)

# Solar radiation calculation function
def calculate_solar_radiation(latitude, longitude, altitude, tilt_angle, day_of_year, timezone):
    # Define the day based on day of year
    date = pd.date_range("2024-01-01", periods=365, freq="D")[day_of_year - 1]
    
    # Create a time range from 6 AM to 6 PM (13 hours inclusive) directly in the target timezone
    # This ensures we always calculate from 6 AM to 6 PM in the local timezone
    start_time = pd.Timestamp.combine(date.date(), time(6, 0)).tz_localize(timezone)
    end_time = pd.Timestamp.combine(date.date(), time(18, 0)).tz_localize(timezone)
    hours = pd.date_range(start=start_time, end=end_time, freq="h")
    
    # Get solar position for each hour
    solpos = get_solarposition(hours, latitude, longitude, altitude)
    zenith_rad = np.radians(solpos["zenith"].clip(upper=90))

    # Calculate air mass with protection against division by zero
    epsilon = 1e-6  # Small value to prevent division by zero
    cos_zenith = np.maximum(np.cos(zenith_rad), epsilon)
    air_mass = (1 / cos_zenith) * np.exp(-0.0001184 * altitude)
    
    # Set a maximum reasonable air mass value
    max_air_mass = 38.0
    air_mass = np.minimum(air_mass, max_air_mass)
    
    # Calculate direct normal irradiance (beam radiation)
    dni = SOLAR_CONSTANT * np.exp(-0.14 * air_mass)
    
    # Apply a gradual cutoff for low sun angles
    sun_factor = np.clip((90 - solpos["zenith"]) / 15, 0, 1)
    dni = dni * sun_factor

    # Calculate diffuse and reflected radiation
    dhi = 0.2 * dni
    cos_theta = np.cos(zenith_rad)
    ghi = dni * cos_theta + dhi
    rhi = 0.1 * ghi

    # Calculate radiation on tilted surface
    poa_global = (
        dni * np.cos(np.radians(tilt_angle)) +
        dhi * ((1 + np.cos(np.radians(tilt_angle))) / 2) +
        rhi * ((1 - np.cos(np.radians(tilt_angle))) / 2)
    )

    # Create dataframe with results
    df = pd.DataFrame({
        "Hour": hours.hour,
        "Beam Radiation (W/m²)": dni,
        "Diffused Radiation (W/m²)": dhi,
        "Reflected Radiation (W/m²)": rhi,
        "Global Radiation (W/m²)": ghi,
        "Total POA Irradiance (W/m²)": poa_global
    })

    return df, df.sum(numeric_only=True)

# Function to plot line graphs with solar theme
def plot_radiation_line(df):
    # Set solar theme for matplotlib
    plt.style.use('default')
    colors = ['#FFA500', '#FFD700', '#87CEEB', '#4682B4']
    
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#FFFAF0')
    ax.set_facecolor('#FFFAF0')
    
    ax.plot(df["Hour"], df["Global Radiation (W/m²)"], label="Global", marker='o', color=colors[0], linewidth=2.5)
    ax.plot(df["Hour"], df["Beam Radiation (W/m²)"], label="Beam", marker='s', color=colors[1], linewidth=2)
    ax.plot(df["Hour"], df["Diffused Radiation (W/m²)"], label="Diffuse", marker='^', color=colors[2], linewidth=2)
    ax.plot(df["Hour"], df["Reflected Radiation (W/m²)"], label="Reflected", marker='d', color=colors[3], linewidth=2)
    
    ax.set_xlabel("Hour", fontsize=12, fontweight='bold')
    ax.set_ylabel("Radiation (W/m²)", fontsize=12, fontweight='bold')
    ax.set_title("Hourly Solar Radiation Components", fontsize=14, fontweight='bold', color='#FFA500')
    
    # Set x-axis to show all hours from 6 to 18
    ax.set_xticks(range(6, 19))
    ax.set_xlim(5.5, 18.5)
    
    # Customize grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Customize legend
    legend = ax.legend(frameon=True, fancybox=True, shadow=True)
    frame = legend.get_frame()
    frame.set_facecolor('white')
    frame.set_edgecolor('#CCCCCC')
    
    return fig

# Function to create a pie chart of radiation components
def plot_radiation_pie(totals):
    labels = ['Beam', 'Diffused', 'Reflected']
    sizes = [
        totals['Beam Radiation (W/m²)'],
        totals['Diffused Radiation (W/m²)'],
        totals['Reflected Radiation (W/m²)']
    ]
    colors = ['#FFD700', '#87CEEB', '#4682B4']
    explode = (0.1, 0, 0)  # explode the 1st slice (Beam)
    
    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor('#FFFAF0')
    ax.set_facecolor('#FFFAF0')
    
    # Check if all values are zero
    if sum(sizes) == 0:
        ax.text(0.5, 0.5, "No radiation data available for this location/date", 
                horizontalalignment='center', verticalalignment='center',
                fontsize=14, fontweight='bold', color='#FFA500')
        ax.axis('off')
    else:
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
               shadow=True, startangle=140, textprops={'fontsize': 12, 'fontweight': 'bold'})
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    
    ax.set_title('Distribution of Solar Radiation Components', fontsize=14, fontweight='bold', color='#FFA500')
    
    return fig

# Function to create a bar chart of hourly radiation
def plot_radiation_bar(df):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#FFFAF0')
    ax.set_facecolor('#FFFAF0')
    
    hours = df["Hour"]
    global_radiation = df["Global Radiation (W/m²)"]
    
    bars = ax.bar(hours, global_radiation, color='#FFA500', alpha=0.7)
    
    # Add a gradient effect to bars
    for i, bar in enumerate(bars):
        bar.set_alpha(0.5 + (i/len(bars))*0.5)
    
    ax.set_xlabel("Hour", fontsize=12, fontweight='bold')
    ax.set_ylabel("Global Radiation (W/m²)", fontsize=12, fontweight='bold')
    ax.set_title("Hourly Global Solar Radiation", fontsize=14, fontweight='bold', color='#FFA500')
    
    # Set x-axis to show all hours from 6 to 18
    ax.set_xticks(range(6, 19))
    ax.set_xlim(5.5, 18.5)
    
    # Customize grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    return fig

# Function to download Excel file
def download_excel(df, totals):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Hourly Radiation Data')
        totals.to_frame().T.to_excel(writer, index=False, sheet_name='Total Daily Radiation')
        
        # Access the workbook and worksheet objects
        workbook = writer.book
        worksheet1 = writer.sheets['Hourly Radiation Data']
        worksheet2 = writer.sheets['Total Daily Radiation']
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#FFA500',
            'border': 1,
            'font_color': 'white'
        })
        
        cell_format = workbook.add_format({
            'border': 1
        })
        
        # Apply formats to the first worksheet
        for col_num, value in enumerate(df.columns.values):
            worksheet1.write(0, col_num, value, header_format)
            
        # Apply formats to the second worksheet
        for col_num, value in enumerate(totals.index.values):
            worksheet2.write(0, col_num, value, header_format)
            
    output.seek(0)
    return output

# Function to get example locations
def get_example_locations():
    return {
        "Custom": {"lat": 0.0, "lon": 0.0, "tz": "UTC"},
        "Cairo, Egypt": {"lat": 30.0444, "lon": 31.2357, "tz": "Africa/Cairo"},
        "New York, USA": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
        "Tokyo, Japan": {"lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
        "Sydney, Australia": {"lat": -33.8688, "lon": 151.2093, "tz": "Australia/Sydney"},
        "London, UK": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
        "Rio de Janeiro, Brazil": {"lat": -22.9068, "lon": -43.1729, "tz": "America/Sao_Paulo"},
        "Cape Town, South Africa": {"lat": -33.9249, "lon": 18.4241, "tz": "Africa/Johannesburg"},
        "Reykjavik, Iceland": {"lat": 64.1466, "lon": -21.9426, "tz": "Atlantic/Reykjavik"}
    }

# Main application
def main():
    # Sidebar for navigation and inputs
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 1rem 0;">
        <h2>☀️ Solar Radiation Dashboard</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Add current date to sidebar
    current_date = datetime.now().strftime("%B %d, %Y")
    st.sidebar.markdown(f"<div style='text-align: center; margin-bottom: 2rem;'>{current_date}</div>", unsafe_allow_html=True)
    
    # Navigation
    page = st.sidebar.radio("Navigation", ["Calculator", "Equations", "About Solar Energy"])
    
    # Example locations
    example_locations = get_example_locations()
    
    # Sidebar inputs (common to all pages)
    st.sidebar.markdown("### Location Settings")
    selected_location = st.sidebar.selectbox(
        "Select Location", 
        list(example_locations.keys()),
        help="Select a predefined location or choose 'Custom' to enter your own coordinates"
    )
    
    # Set location values based on selection
    if selected_location != "Custom":
        location = example_locations[selected_location]
        latitude = st.sidebar.number_input("Latitude (°)", value=location["lat"], min_value=-90.0, max_value=90.0)
        longitude = st.sidebar.number_input("Longitude (°)", value=location["lon"], min_value=-180.0, max_value=180.0)
        timezone = st.sidebar.text_input("Timezone", value=location["tz"])
    else:
        latitude = st.sidebar.number_input("Latitude (°)", value=0.0, min_value=-90.0, max_value=90.0)
        longitude = st.sidebar.number_input("Longitude (°)", value=0.0, min_value=-180.0, max_value=180.0)
        timezone = st.sidebar.text_input("Timezone (e.g., 'Africa/Cairo')", value="UTC")
    
    st.sidebar.markdown("### Solar Panel Settings")
    altitude = st.sidebar.number_input("Altitude (m)", value=0)
    tilt_angle = st.sidebar.slider("Panel Tilt Angle (°)", min_value=0, max_value=90, value=30)
    
    st.sidebar.markdown("### Time Settings")
    day_of_year = st.sidebar.slider("Day of Year", min_value=1, max_value=365, value=172)
    
    # Main content based on selected page
    if page == "Calculator":
        # Main content area
        st.markdown("<h1 style='text-align: center;'>Solar Radiation Calculator</h1>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-box">
            <p>This calculator uses physics-based models to estimate solar radiation components for a specific location and time.
            Adjust the parameters in the sidebar and click 'Calculate' to see the results.</p>
            <p><strong>Note:</strong> Calculations are performed for the time range from 6 AM to 6 PM in the local timezone.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Calculate button
        if st.button("Calculate Solar Radiation"):
            with st.spinner("Calculating solar radiation..."):
                try:
                    df, totals = calculate_solar_radiation(latitude, longitude, altitude, tilt_angle, day_of_year, timezone)
                    
                    # Check if we have any significant radiation
                    has_radiation = totals['Global Radiation (W/m²)'] > 1.0
                    
                    # Display results in a dashboard layout
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                        st.subheader("☀️ Total Daily Radiation")
                        st.dataframe(totals.to_frame().T.style.background_gradient(cmap="YlOrRd"))
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                        st.subheader("📊 Radiation Distribution")
                        pie_fig = plot_radiation_pie(totals)
                        st.pyplot(pie_fig)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                        st.subheader("📈 Hourly Radiation Graph")
                        line_fig = plot_radiation_line(df)
                        st.pyplot(line_fig)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                        st.subheader("📊 Hourly Global Radiation")
                        bar_fig = plot_radiation_bar(df)
                        st.pyplot(bar_fig)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Data table in full width
                    st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                    st.subheader("📋 Hourly Radiation Data")
                    st.dataframe(df.style.background_gradient(cmap="YlOrRd", subset=['Global Radiation (W/m²)', 'Total POA Irradiance (W/m²)']))
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Warning for low/zero radiation
                    if not has_radiation:
                        st.markdown("""
                        <div class="warning-box">
                            <h3>⚠️ Very low or zero radiation detected</h3>
                            <p>This could be due to:</p>
                            <ul>
                                <li>The sun being below the horizon for this location during winter months</li>
                                <li>Extreme latitude locations during certain times of year</li>
                                <li>Incorrect timezone setting</li>
                            </ul>
                            <p>Try adjusting the day of year or checking a different location.</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Download button
                    excel_file = download_excel(df, totals)
                    st.download_button(
                        label="📥 Download Excel Report", 
                        data=excel_file, 
                        file_name=f"solar_radiation_{latitude}_{longitude}_{day_of_year}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.info("Please check your inputs, especially the timezone value.")
    
    elif page == "Equations":
        st.markdown("<h1 style='text-align: center;'>Solar Radiation Equations</h1>", unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("1. Zenith Angle")
        st.latex(r"\cos(\theta_z) = \sin(\phi) \cdot \sin(\delta) + \cos(\phi) \cdot \cos(\delta) \cdot \cos(H)")
        st.markdown("""
        Where:
        - $\\theta_z$ is the solar zenith angle
        - $\\phi$ is the latitude
        - $\\delta$ is the solar declination
        - $H$ is the hour angle
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("2. Air Mass")
        st.latex(r"AM = \frac{1}{\cos(\theta_z)} \cdot e^{-k \cdot h}")
        st.markdown("""
        Where:
        - $AM$ is the air mass
        - $\\theta_z$ is the solar zenith angle
        - $k$ is the altitude coefficient (0.0001184)
        - $h$ is the altitude above sea level
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("3. Beam Radiation")
        st.latex(r"I_b = G_{sc} \cdot e^{-a\cdot AM}")
        st.markdown("""
        Where:
        - $I_b$ is the beam radiation
        - $G_{sc}$ is the solar constant (1367 W/m²)
        - $a$ is the atmospheric attenuation coefficient (0.14)
        - $AM$ is the air mass
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("4. Diffuse Radiation")
        st.latex(r"I_d = 0.2 \cdot I_b")
        st.markdown("""
        Where:
        - $I_d$ is the diffuse radiation
        - $I_b$ is the beam radiation
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("5. Reflected Radiation")
        st.latex(r"I_r = 0.1 \cdot (I_b \cdot \cos(\theta_z) + I_d)")
        st.markdown("""
        Where:
        - $I_r$ is the reflected radiation
        - $I_b$ is the beam radiation
        - $\\theta_z$ is the solar zenith angle
        - $I_d$ is the diffuse radiation
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card">', unsafe_allow_html=True)
        st.subheader("6. Tilted Surface Radiation")
        st.latex(r"I_{b,t} = I_b \cdot \cos(\theta)")
        st.latex(r"I_{d,t} = I_d \cdot \frac{1+\cos(\beta)}{2}")
        st.latex(r"I_{r,t} = I_r \cdot \frac{1-\cos(\beta)}{2}")
        st.markdown("""
        Where:
        - $I_{b,t}$ is the beam radiation on tilted surface
        - $I_{d,t}$ is the diffuse radiation on tilted surface
        - $I_{r,t}$ is the reflected radiation on tilted surface
        - $\\theta$ is the angle of incidence
        - $\\beta$ is the tilt angle
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "About Solar Energy":
        st.markdown("<h1 style='text-align: center;'>About Solar Energy</h1>", unsafe_allow_html=True)
        
        # Create tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Radiation Components", "Factors", "Applications"])
        
        with tab1:
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("What is Solar Energy?")
            st.markdown("""
            Solar energy is radiant light and heat from the Sun that is harnessed using a range of technologies such as:
            - Solar photovoltaics
            - Solar thermal energy
            - Solar architecture
            - Artificial photosynthesis
            
            It is an essential source of renewable energy, and its technologies are broadly characterized as either passive or active solar depending on how they capture and distribute solar energy or convert it into solar power.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                st.subheader("Importance of Solar Energy")
                st.markdown("""
                Solar energy is one of the cleanest and most abundant renewable energy sources available. Modern technology can harness this energy for a variety of uses, including:
                
                - Generating electricity
                - Providing light
                - Heating water
                - Heating and cooling spaces
                
                Solar energy systems don't produce air pollutants or greenhouse gases, making them environmentally friendly alternatives to fossil fuels.
                """)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="solar-card">', unsafe_allow_html=True)
                st.subheader("Solar Energy Growth")
                st.markdown("""
                The solar energy industry has experienced rapid growth in recent decades:
                
                - Global solar capacity has increased exponentially
                - Solar panel costs have decreased by more than 70% since 2010
                - Many countries are setting ambitious solar energy targets
                - Technological innovations continue to improve efficiency
                
                This growth is driven by environmental concerns, decreasing costs, and supportive government policies.
                """)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with tab2:
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Solar Radiation Components")
            st.markdown("""
            Solar radiation reaching the Earth's surface consists of three main components:
            
            1. **Direct (Beam) Radiation**: Sunlight that travels in a straight line from the sun to the Earth's surface without being scattered.
            
            2. **Diffuse Radiation**: Sunlight that has been scattered by molecules and particles in the atmosphere but still reaches the Earth's surface.
            
            3. **Reflected Radiation**: Sunlight that is reflected off non-atmospheric features such as the ground.
            
            The sum of all three components is called **Global Radiation**.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Understanding Zero Radiation Values")
            st.markdown("""
            There are several reasons why solar radiation calculations might show zero or very low values:
            
            1. **Sun Below Horizon**: When the sun is below the horizon (night time or early morning/late evening), no direct radiation reaches the surface.
            
            2. **Seasonal Variations**: In locations far from the equator, winter months have shorter days and the sun's position is lower in the sky, resulting in less radiation.
            
            3. **Polar Regions**: Near the poles, there are periods of the year with no sunlight (polar night) or constant sunlight (midnight sun).
            
            4. **Time Zone Settings**: Incorrect time zone settings can shift the calculation period away from daylight hours.
            
            This calculator shows radiation values from 6 AM to 6 PM local time. For accurate results, ensure your location and time zone settings are correct.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab3:
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Factors Affecting Solar Radiation")
            st.markdown("""
            Several factors affect the amount of solar radiation reaching a specific location:
            
            - **Geographic location**: Latitude and longitude determine the sun's path across the sky.
            - **Time of year**: The Earth's tilt causes seasonal variations in solar radiation.
            - **Time of day**: The sun's position in the sky changes throughout the day.
            - **Atmospheric conditions**: Clouds, pollution, and humidity affect radiation transmission.
            - **Altitude**: Higher altitudes receive more radiation due to less atmospheric filtering.
            - **Surface orientation**: The angle at which radiation strikes a surface affects energy absorption.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Optimizing Solar Panel Tilt")
            st.markdown("""
            The tilt angle of a solar panel significantly affects its energy production:
            
            - **Latitude-based rule**: A common rule of thumb is to set the tilt angle equal to the latitude for year-round optimization.
            - **Seasonal adjustment**: Increase tilt by 15° in winter and decrease by 15° in summer for seasonal optimization.
            - **Local factors**: Adjustments may be needed based on local weather patterns and shading.
            - **Fixed vs. tracking systems**: While fixed systems use a compromise angle, tracking systems follow the sun for maximum efficiency.
            
            This calculator allows you to experiment with different tilt angles to find the optimal setting for your location and time of year.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab4:
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Solar Energy Applications")
            st.markdown("""
            Solar energy has numerous applications:
            
            - **Electricity generation**: Using photovoltaic cells to convert sunlight directly into electricity.
            - **Water heating**: Solar thermal collectors heat water for residential and commercial use.
            - **Space heating and cooling**: Solar energy can be used for both heating and cooling buildings.
            - **Transportation**: Solar-powered vehicles and charging stations for electric vehicles.
            - **Desalination**: Using solar energy to remove salt from seawater.
            - **Industrial processes**: Providing heat for manufacturing processes.
            """)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="solar-card">', unsafe_allow_html=True)
            st.subheader("Solar Energy Storage")
            st.markdown("""
            Energy storage is crucial for making solar power available when the sun isn't shining:
            
            - **Battery storage**: Lithium-ion and other battery technologies store electricity for later use.
            - **Thermal storage**: Heat can be stored in materials like molten salt for later electricity generation.
            - **Pumped hydro storage**: Water is pumped uphill during sunny periods and released to generate electricity when needed.
            - **Hydrogen production**: Solar electricity can produce hydrogen through electrolysis for long-term storage.
            
            Advances in storage technology are making solar energy increasingly reliable as a primary power source.
            """)
            st.markdown('</div>', unsafe_allow_html=True)

# Run the application
if __name__ == "__main__":
    main()
