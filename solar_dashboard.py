import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from pvlib.solarposition import get_solarposition
from pvlib.irradiance import get_total_irradiance
import pytz
from datetime import datetime, time
import base64
from geopy.geocoders import Nominatim

# Constants
SOLAR_CONSTANT = 1367  # W/m^2

# Set page configuration
st.set_page_config(
    page_title="Global Solar Still Radiation Dashboard",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for solar theme
def add_solar_theme():
    st.markdown("""
    <style>
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
        .stApp { background: linear-gradient(135deg, var(--solar-light-bg) 0%, #FFFCF5 100%); }
        h1, h2, h3 { color: var(--solar-orange) !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
        .stButton>button {
            background: linear-gradient(90deg, var(--solar-yellow) 0%, var(--solar-orange) 100%);
            color: var(--solar-text); border: none; font-weight: bold; border-radius: 10px;
        }
        .solar-card {
            background-color: white; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            padding: 20px; margin-bottom: 20px; border-left: 5px solid var(--solar-orange);
        }
        .sun-icon {
            display: inline-block; width: 50px; height: 50px; background-color: var(--solar-yellow);
            border-radius: 50%; animation: sun-glow 3s infinite; position: absolute; top: 20px; right: 20px; z-index: 1000;
        }
        @keyframes sun-glow {
            0% { box-shadow: 0 0 10px 5px rgba(255, 215, 0, 0.5); }
            50% { box-shadow: 0 0 20px 10px rgba(255, 215, 0, 0.7); }
            100% { box-shadow: 0 0 10px 5px rgba(255, 215, 0, 0.5); }
        }
    </style>
    <div class="sun-icon"></div>
    """, unsafe_allow_html=True)

add_solar_theme()

# Solar radiation calculation function
def calculate_solar_radiation(latitude, longitude, altitude, tilt_angle, day_of_year, timezone_str):
    try:
        timezone = pytz.timezone(timezone_str)
    except Exception as e:
        st.error(f"Invalid Timezone: {timezone_str}. Falling back to UTC.")
        timezone = pytz.UTC

    date = pd.date_range("2024-01-01", periods=365, freq="D")[day_of_year - 1]
    
    start_time = pd.Timestamp.combine(date.date(), time(6, 0)).tz_localize(timezone, nonexistent='shift_forward')
    end_time = pd.Timestamp.combine(date.date(), time(18, 0)).tz_localize(timezone, nonexistent='shift_forward')
    hours = pd.date_range(start=start_time, end=end_time, freq="h")
    
    solpos = get_solarposition(hours, latitude, longitude, altitude)
    zenith_rad = np.radians(solpos["zenith"].clip(upper=90))
    
    epsilon = 1e-6
    cos_zenith = np.maximum(np.cos(zenith_rad), epsilon)
    air_mass = (1 / cos_zenith) * np.exp(-0.0001184 * altitude)
    air_mass = np.minimum(air_mass, 38.0)
    
    reference_day = 172 if latitude >= 0 else 355
    seasonal_phase = 2 * np.pi * (day_of_year - reference_day) / 365
    # Empirical seasonal calibration for atmospheric transmittance
    dynamic_transmittance = 0.70 - (0.08 * np.cos(seasonal_phase))
    
    dni = SOLAR_CONSTANT * (dynamic_transmittance ** (air_mass ** 0.678))
    sun_factor = np.clip((90 - solpos["zenith"]) / 15, 0, 1)
    dni = dni * sun_factor

    diffuse_fraction = 0.15 + (0.05 * np.cos(seasonal_phase + np.pi))
    beam_horizontal = dni * np.cos(zenith_rad)
    dhi = diffuse_fraction * beam_horizontal
    ghi = beam_horizontal + dhi
    
    surface_azimuth = 180 if latitude >= 0 else 0

    poa_components = get_total_irradiance(
        surface_tilt=tilt_angle,
        surface_azimuth=surface_azimuth,
        solar_zenith=solpos['zenith'],
        solar_azimuth=solpos['azimuth'],
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        albedo=0.2 
    )

    df = pd.DataFrame({
        "Hour": hours.hour,
        "Beam Radiation on Glass Cover (W/m²)": poa_components['poa_direct'],
        "Diffuse Radiation on Glass Cover (W/m²)": poa_components['poa_sky_diffuse'],
        "Reflected Radiation on Glass Cover (W/m²)": poa_components['poa_ground_diffuse'],
        "Total POA Irradiance on Glass Cover (W/m²)": poa_components['poa_global']
    })
    
    df = df.round(2)
    return df, df.sum(numeric_only=True).round(2)

# Plotting functions
def plot_radiation_line(df):
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#FFFAF0')
    ax.set_facecolor('#FFFAF0')
    colors = ['#FFA500', '#FFD700', '#87CEEB', '#4682B4']
    
    ax.plot(df["Hour"], df["Total POA Irradiance on Glass Cover (W/m²)"], label="Total POA", marker='o', color=colors[0], linewidth=2.5)
    ax.plot(df["Hour"], df["Beam Radiation on Glass Cover (W/m²)"], label="Beam (Glass)", marker='s', color=colors[1], linewidth=2)
    ax.plot(df["Hour"], df["Diffuse Radiation on Glass Cover (W/m²)"], label="Diffuse (Glass)", marker='^', color=colors[2], linewidth=2)
    ax.plot(df["Hour"], df["Reflected Radiation on Glass Cover (W/m²)"], label="Reflected (Glass)", marker='d', color=colors[3], linewidth=2)
    
    ax.set_xlabel("Hour", fontweight='bold')
    ax.set_ylabel("Radiation (W/m²)", fontweight='bold')
    ax.set_title("Hourly Solar Radiation on Glass Cover", fontweight='bold', color='#FFA500')
    ax.set_xticks(range(6, 19))
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(frameon=True, shadow=True)
    return fig

def plot_radiation_pie(totals):
    labels = ['Beam (Glass)', 'Diffuse (Glass)', 'Reflected (Glass)']
    sizes = [
        totals["Beam Radiation on Glass Cover (W/m²)"],
        totals["Diffuse Radiation on Glass Cover (W/m²)"],
        totals["Reflected Radiation on Glass Cover (W/m²)"]
    ]
    colors = ['#FFD700', '#87CEEB', '#4682B4']
    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor('#FFFAF0')
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=140)
    ax.set_title('Radiation Distribution on Glass Cover', fontweight='bold', color='#FFA500')
    return fig

def plot_radiation_bar(df):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#FFFAF0')
    ax.bar(df["Hour"], df["Total POA Irradiance on Glass Cover (W/m²)"], color='#FFD700', edgecolor='#FFA500')
    ax.set_title("Hourly Total POA Radiation", fontweight='bold', color='#FFA500')
    ax.set_xticks(range(6, 19))
    return fig

def download_excel(df, totals):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Hourly_Data')
        totals.to_frame().T.to_excel(writer, index=False, sheet_name='Daily_Totals')
    return output.getvalue()

# --- Sidebar Layout ---
st.sidebar.markdown('<div style="text-align: center;"><h2>☀️ Solar Still Settings</h2></div>', unsafe_allow_html=True)

st.sidebar.markdown("### 📍 Location Settings")
country_name = st.sidebar.text_input("Country Name", "Egypt")
city_name = st.sidebar.text_input("City Name", "Cairo")

geolocator = Nominatim(user_agent="solar_still_app")
default_lat, default_lon, default_alt = 30.04, 31.23, 23
default_tz = "Africa/Cairo"

if st.sidebar.button("Fetch Location Data"):
    try:
        location = geolocator.geocode(f"{city_name}, {country_name}")
        if location:
            default_lat = location.latitude
            default_lon = location.longitude
            st.sidebar.success(f"Found: {location.address}")
        else:
            st.sidebar.error("Location not found. Using defaults.")
    except:
        st.sidebar.error("Geocoding service unavailable.")

latitude = st.sidebar.number_input("Latitude (°)", value=default_lat, step=0.01, format="%.2f")
longitude = st.sidebar.number_input("Longitude (°)", value=default_lon, step=0.01, format="%.2f")
altitude = st.sidebar.number_input("Altitude (m)", value=default_alt, step=1)

st.sidebar.markdown("### 🕒 Timezone Settings")
tz_option = st.sidebar.radio("Timezone Selection", ["Select from List", "Enter Manually"])
if tz_option == "Select from List":
    all_tz = pytz.all_timezones
    try: default_tz_idx = all_tz.index(default_tz)
    except: default_tz_idx = 0
    timezone_input = st.sidebar.selectbox("Choose Timezone", all_tz, index=default_tz_idx)
else:
    timezone_input = st.sidebar.text_input("Enter Timezone (e.g., Africa/Cairo, UTC)", value=default_tz)

st.sidebar.markdown("### 📐 Solar Still Settings")
tilt_angle = st.sidebar.slider("Glass Cover Tilt Angle (°)", 0, 90, 30)
st.sidebar.info(f"Panel Azimuth: {'180° (South)' if latitude >= 0 else '0° (North)'}")

st.sidebar.markdown("### 📅 Time Settings")
day_of_year = st.sidebar.slider("Day of Year", 1, 365, datetime.now().timetuple().tm_yday)

page = st.sidebar.radio("Go to", ["Dashboard", "Equations", "About Solar Energy"])

# --- Main Pages ---
if page == "Dashboard":
    st.markdown(f"<h1>☀️ Solar Still Radiation Dashboard - {city_name}, {country_name}</h1>", unsafe_allow_html=True)
    
    if st.button("Calculate Solar Radiation"):
        df, totals = calculate_solar_radiation(latitude, longitude, altitude, tilt_angle, day_of_year, timezone_input)
        
        col_graphs, col_tables = st.columns([1, 1])
        
        with col_graphs:
            st.markdown('<div class="solar-card"><h3>📈 Hourly Radiation Graph</h3>', unsafe_allow_html=True)
            st.pyplot(plot_radiation_line(df))
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="solar-card"><h3>📊 Hourly Total POA Radiation</h3>', unsafe_allow_html=True)
            st.pyplot(plot_radiation_bar(df))
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="solar-card"><h3>📊 Radiation Distribution</h3>', unsafe_allow_html=True)
            st.pyplot(plot_radiation_pie(totals))
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_tables:
            st.markdown('<div class="solar-card"><h3>☀️ Total Daily Radiation</h3>', unsafe_allow_html=True)
            display_totals = totals.to_frame().T.drop(columns=['Hour'], errors='ignore')
            st.dataframe(display_totals.style.format("{:.2f}"))
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="solar-card"><h3>📋 Hourly Radiation Data (6 AM - 6 PM)</h3>', unsafe_allow_html=True)
            st.dataframe(df.style.format("{:.2f}").background_gradient(cmap="YlOrRd", subset=['Total POA Irradiance on Glass Cover (W/m²)']))
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.download_button("📥 Download Excel Report", download_excel(df, totals), "solar_still_report.xlsx")

elif page == "Equations":
    st.markdown("<h1>Solar Radiation Equations & Parameters</h1>", unsafe_allow_html=True)
    
    st.markdown('<div class="solar-card"><h3>1. Empirical Seasonal Atmospheric Transmittance</h3>', unsafe_allow_html=True)
    st.latex(r"\tau(d) = 0.70 - 0.08 \cdot \cos\left(\frac{2\pi(d-d_{solstice})}{365}\right)")
    st.markdown(r"""
    **Explanation:**
    This empirical correlation was introduced to account for seasonal variations in atmospheric clarity throughout the year. It is used as a calibration factor to improve the realism of estimated solar radiation.
    - $\tau(d)$: The dynamic transmittance (transmissivity) for a clear sky on day $d$.
    - **0.70:** Base transmittance for a clear sky.
    - **0.08:** Amplitude of seasonal variation.
    - **d:** Current day of the year (1-365).
    - **d_solstice:** Solstice reference day (172 for North, 355 for South).
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="solar-card"><h3>2. Zenith Angle (θz)</h3>', unsafe_allow_html=True)
    st.latex(r"\cos(\theta_z) = \sin(\phi) \cdot \sin(\delta) + \cos(\phi) \cdot \cos(\delta) \cdot \cos(H)")
    st.markdown(r"""
    **Parameters:**
    - $\phi$ (Latitude): The angular distance North or South of the equator.
    - $\delta$ (Declination): The angle between the sun's rays and the Earth's equatorial plane.
    - $H$ (Hour Angle): The angular displacement of the sun East or West of the local meridian.
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="solar-card"><h3>3. Air Mass (AM)</h3>', unsafe_allow_html=True)
    st.latex(r"AM = \frac{1}{\cos(\theta_z)} \cdot e^{-0.0001184 \cdot h}")
    st.markdown(r"""
    **Parameters:**
    - $\theta_z$: Zenith angle.
    - $h$: Altitude in meters.
    - **0.0001184:** Atmospheric pressure decay constant.
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="solar-card"><h3>4. Beam Radiation (Ib) - Modified Clear-Sky Model</h3>', unsafe_allow_html=True)
    st.latex(r"I_b = G_{sc} \cdot \tau(d)^{\,AM^{0.678}}")
    st.markdown(r"""
    **Parameters:**
    Beam radiation estimated using an empirical atmospheric transmittance model combined with air mass correction.
    - $G_{sc}$ (Solar Constant): 1367 W/m².
    - $\tau(d)$: Dynamic transmittance calculated in Eq 1.
    - $AM$: Air Mass.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="solar-card"><h3>5. ASHRAE Clear-Sky Model (Reference Model)</h3>', unsafe_allow_html=True)
    st.latex(r"I_b = A \cdot e^{-B / \sin(\beta)}")
    st.markdown(r"""
    **Parameters:**
    - $I_b$: Direct normal irradiance (W/m²).
    - $A$: Apparent extraterrestrial radiation (location- and month-dependent coefficient from ASHRAE tables).
    - $B$: Atmospheric extinction coefficient (location- and month-dependent coefficient from ASHRAE tables).
    - $\beta$: Solar altitude angle.

    **Note:** This is the standard ASHRAE clear-sky formulation, shown here as a reference model.
    The model implemented in this dashboard (Eq. 1 and Eq. 4) is a separate empirical
    transmittance approach calibrated for seasonal variation, and is **not** a direct
    application of the ASHRAE A/B coefficient tables. The ASHRAE formulation is included
    here for comparison and academic reference only.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="solar-card"><h3>6. Tilted Surface (POA)</h3>', unsafe_allow_html=True)
    st.latex(r"POA_{Total} = I_{beam,t} + I_{diffuse,t} + I_{reflected,t}")
    st.markdown(r"""
    **Parameters:**
    - $I_{beam,t}$: Direct beam hitting the glass.
    - $I_{diffuse,t}$: Scattered light hitting the glass.
    - $I_{reflected,t}$: Light reflected from the ground onto the glass.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

elif page == "About Solar Energy":
    st.markdown("<h1 style='text-align: center;'>About Solar Energy</h1>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Radiation Components", "Factors", "Applications"])
    
    with tab1:
        st.markdown('<div class="solar-card"><h3>What is Solar Energy?</h3>', unsafe_allow_html=True)
        st.markdown("Solar energy is radiant light and heat from the Sun harnessed using various technologies.")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        st.markdown('<div class="solar-card"><h3>Solar Radiation Components</h3>', unsafe_allow_html=True)
        st.markdown("1. Direct (Beam) Radiation\n2. Diffuse Radiation\n3. Reflected Radiation")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab3:
        st.markdown('<div class="solar-card"><h3>Factors Affecting Solar Radiation</h3>', unsafe_allow_html=True)
        st.markdown("- Geographic location\n- Time of year\n- Time of day\n- Atmospheric conditions")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab4:
        st.markdown('<div class="solar-card"><h3>Solar Energy Applications</h3>', unsafe_allow_html=True)
        st.markdown("- Electricity generation\n- Water heating\n- Solar distillation")
        st.markdown('</div>', unsafe_allow_html=True)
