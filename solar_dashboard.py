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
    page_title="Solar Radiation Calculator",
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

# ──────────────────────────────────────────────────────────────────────────
# FIX: Column names below are now spelled IDENTICALLY everywhere in the file
# (DataFrame creation, every plotting function, and the results tables).
# The original bug was a column created as "Diffuse Radiation (W/m²)"
# (one space) but read back as "Diffuse Radiation  (W/m²)" (two spaces) —
# Python/pandas treats these as two completely different column names,
# which raised KeyError: 'Diffuse Radiation  (W/m²)' at runtime.
# Fixed names (single space before the unit, used consistently everywhere):
#   "Beam Radiation (W/m²)"
#   "Diffuse Radiation (W/m²)"
#   "Reflected Radiation (W/m²)"
#   "Total POA Irradiance (W/m²)"
# ──────────────────────────────────────────────────────────────────────────

COL_BEAM = "Beam Radiation (W/m²)"
COL_DIFFUSE = "Diffuse Radiation (W/m²)"
COL_REFLECTED = "Reflected Radiation (W/m²)"
COL_POA = "Total POA Irradiance (W/m²)"

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
        COL_BEAM: poa_components['poa_direct'],
        COL_DIFFUSE: poa_components['poa_sky_diffuse'],
        COL_REFLECTED: poa_components['poa_ground_diffuse'],
        COL_POA: poa_components['poa_global']
    })
    
    df = df.round(2)
    totals = df.drop(columns=["Hour"]).sum(numeric_only=True).round(2)
    return df, totals

# ──────────────────────────────────────────────────────────────────────────
# Plotting functions — clean, minimal, professional style
# ──────────────────────────────────────────────────────────────────────────

# Shared professional color palette
C_POA = "#E8741C"       # warm orange — primary series
C_BEAM = "#F2B705"      # amber
C_DIFFUSE = "#5DADE2"   # soft blue
C_REFLECTED = "#5D6D7E" # slate gray
GRID_COLOR = "#E5E5E5"
TEXT_COLOR = "#333333"

def _apply_clean_style(ax, fig):
    """Shared minimal/professional styling for all charts."""
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#CCCCCC')
    ax.grid(True, linestyle='-', linewidth=0.6, color=GRID_COLOR, alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXT_COLOR, labelsize=10)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)

def plot_radiation_line(df):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    
    ax.plot(df["Hour"], df[COL_POA], label="Total POA", color=C_POA, linewidth=2.4, marker='o', markersize=4)
    ax.plot(df["Hour"], df[COL_BEAM], label="Beam", color=C_BEAM, linewidth=1.6, marker='o', markersize=3, alpha=0.85)
    ax.plot(df["Hour"], df[COL_DIFFUSE], label="Diffuse", color=C_DIFFUSE, linewidth=1.6, marker='o', markersize=3, alpha=0.85)
    ax.plot(df["Hour"], df[COL_REFLECTED], label="Reflected", color=C_REFLECTED, linewidth=1.6, marker='o', markersize=3, alpha=0.85)

    ax.set_xlabel("Hour", fontsize=11, fontweight='medium')
    ax.set_ylabel("Radiation (W/m²)", fontsize=11, fontweight='medium')
    ax.set_title("Hourly Solar Radiation", fontsize=13, fontweight='bold', color=TEXT_COLOR, loc='left', pad=12)
    ax.set_xticks(range(6, 19))

    legend = ax.legend(frameon=False, fontsize=10, loc='upper left', bbox_to_anchor=(0, -0.18), ncol=4)

    _apply_clean_style(ax, fig)
    fig.tight_layout()
    return fig

def plot_radiation_pie(totals):
    labels = ['Beam', 'Diffuse', 'Reflected']
    sizes = [totals[COL_BEAM], totals[COL_DIFFUSE], totals[COL_REFLECTED]]
    colors = [C_BEAM, C_DIFFUSE, C_REFLECTED]

    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor('white')

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct='%1.1f%%',
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2),
        textprops=dict(fontsize=11, color=TEXT_COLOR)
    )
    for at in autotexts:
        at.set_color('white')
        at.set_fontweight('bold')
        at.set_fontsize(10)

    ax.set_title('Radiation Distribution', fontsize=13, fontweight='bold', color=TEXT_COLOR, pad=12)
    fig.tight_layout()
    return fig

def plot_radiation_bar(df):
    fig, ax = plt.subplots(figsize=(9, 4.5))

    ax.bar(df["Hour"], df[COL_POA], color=C_POA, width=0.6, edgecolor='none')

    ax.set_xlabel("Hour", fontsize=11, fontweight='medium')
    ax.set_ylabel("Total POA Radiation (W/m²)", fontsize=11, fontweight='medium')
    ax.set_title("Hourly Total POA Radiation", fontsize=13, fontweight='bold', color=TEXT_COLOR, loc='left', pad=12)
    ax.set_xticks(range(6, 19))

    _apply_clean_style(ax, fig)
    fig.tight_layout()
    return fig

def download_excel(df, totals):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Hourly_Data')
        totals.to_frame().T.to_excel(writer, index=False, sheet_name='Daily_Totals')
    return output.getvalue()

# --- Sidebar Layout ---
# FIX: renamed from "Solar Still Settings" to a general-purpose title,
# since this sidebar section configures the calculator itself (location,
# timezone, tilt, date) and isn't specific to a solar still.
st.sidebar.markdown('<div style="text-align: center;"><h2>☀️ Radiation Calculator Settings</h2></div>', unsafe_allow_html=True)

# ── Live current date, shown at the very top of the sidebar ──────────────
current_datetime = datetime.now().strftime("%B %d, %Y — %I:%M %p")
st.sidebar.markdown(
    f"<div style='text-align:center; color:#777; margin-bottom:0.5rem;'>🕒 {current_datetime}</div>",
    unsafe_allow_html=True
)

# ── Navigation, placed right below the date ───────────────────────────────
page = st.sidebar.radio("Go to", ["Dashboard", "Equations", "About Solar Energy"])

st.sidebar.markdown("---")

st.sidebar.markdown("### 📍 Location Settings")
country_name = st.sidebar.text_input("Country Name", "Egypt")
city_name = st.sidebar.text_input("City Name", "Cairo")

geolocator = Nominatim(user_agent="solar_radiation_app")
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

st.sidebar.markdown("### 📐 Panel / Surface Settings")
tilt_angle = st.sidebar.slider("Surface Tilt Angle (°)", 0, 90, 30)
st.sidebar.info(f"Panel Azimuth: {'180° (South)' if latitude >= 0 else '0° (North)'}")

st.sidebar.markdown("### 📅 Time Settings")
day_of_year = st.sidebar.slider("Day of Year", 1, 365, datetime.now().timetuple().tm_yday)

# --- Main Pages ---
if page == "Dashboard":
    st.markdown(f"<h1>☀️ Solar Radiation Dashboard - {city_name}, {country_name}</h1>", unsafe_allow_html=True)
    
    if st.button("Calculate Solar Radiation"):
        df, totals = calculate_solar_radiation(latitude, longitude, altitude, tilt_angle, day_of_year, timezone_input)
        
        # ── Professional layout order ─────────────────────────────────
        # 1) Main hourly chart      — the big picture first
        # 2) Hourly data table      — detailed numbers
        # 3) Total daily radiation  — summary, directly below detail
        # 4) Bar chart              — secondary visual
        # 5) Distribution pie chart — supporting breakdown, last
        
        st.markdown('<div class="solar-card"><h3>📈 Hourly Radiation Graph</h3>', unsafe_allow_html=True)
        st.pyplot(plot_radiation_line(df))
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card"><h3>📋 Hourly Radiation Data (6 AM - 6 PM)</h3>', unsafe_allow_html=True)
        st.dataframe(df.style.format("{:.2f}").background_gradient(cmap="YlOrRd", subset=[COL_POA]), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="solar-card"><h3>☀️ Total Daily Radiation</h3>', unsafe_allow_html=True)
        display_totals = totals.to_frame().T
        st.dataframe(display_totals.style.format("{:.2f}"), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.download_button("📥 Download Excel Report", download_excel(df, totals), "solar_radiation_report.xlsx")
        
        st.markdown('<div class="solar-card"><h3>📊 Hourly Total POA Radiation</h3>', unsafe_allow_html=True)
        st.pyplot(plot_radiation_bar(df))
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="solar-card"><h3>📊 Radiation Distribution</h3>', unsafe_allow_html=True)
        st.pyplot(plot_radiation_pie(totals))
        st.markdown('</div>', unsafe_allow_html=True)

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
