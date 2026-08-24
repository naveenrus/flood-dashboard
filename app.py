# =========================================================
# app.py
# =========================================================

import os
import time
import streamlit as st
import modules.flood_module as fm

st.set_page_config(
    page_title="Near-Real-Time SAR Sentinel Flood Monitoring Portal",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling & Viewport Scroll Lock
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
        overflow-anchor: none !important;
        scroll-behavior: auto !important;
    }
    
    .block-container {
        padding-top: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        padding-bottom: 0rem !important;
        max-width: 98% !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent !important;}

    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #0284c7;
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .metric-label {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 18px;
        font-weight: 800;
        color: #0f172a;
        margin-top: 2px;
    }
    </style>
""", unsafe_allow_html=True)

# Centered Modern Header Banner
st.markdown("""
    <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 10px 20px;
        border-radius: 8px;
        border: 1px solid #334155;
        margin-bottom: 8px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    ">
        <div style="
            font-family: 'Inter', sans-serif;
            font-size: 20px;
            font-weight: 800;
            color: #f8fafc;
            margin: 0;
            letter-spacing: -0.5px;
            text-align: center;
        ">
            🌊 Advanced Flood Mapping System
        </div>
        <div style="
            position: absolute;
            right: 20px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(52, 211, 153, 0.3);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
        ">
            ● ENGINE ONLINE
        </div>
    </div>
""", unsafe_allow_html=True)

# Technical Metadata Ribbon
st.markdown("""
    <div style="
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-around;
        gap: 12px;
        background: #0f172a;
        border: 1px solid #1e293b;
        color: #94a3b8;
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        font-family: monospace;
        font-size: 11px;
        box-sizing: border-box;
        width: 100%;
    ">
        <div style="white-space: nowrap;">🛰️ <b>SENSOR:</b> Sentinel-1 C-Band SAR (VV + VH)</div>
        <div style="white-space: nowrap;">⚡ <b>PROCESSING:</b> Speckle Filtered & DEM Masked</div>
        <div style="white-space: nowrap;">🌐 <b>ENGINE:</b> Google Earth Engine (10m Native)</div>
    </div>
""", unsafe_allow_html=True)

if "result" not in st.session_state:
    st.session_state.result = None

# Fetch district and state lists dynamically
districts, states = fm.get_admin_lists()

# =========================================================
# SIDEBAR CONTROLS
# =========================================================
with st.sidebar:
    st.markdown("### 🎯 Spatial Query Controls")

    mode = st.radio(
        "Select Administrative Level",
        ["district", "state"],
        format_func=lambda x: x.capitalize()
    )

    if mode == "district":
        default_idx = districts.index("FARRUKHABAD") if "FARRUKHABAD" in districts else 0
        name = st.selectbox("Select District Name", districts, index=default_idx)
    else:
        default_idx = states.index("UTTAR PRADESH") if "UTTAR PRADESH" in states else 0
        name = st.selectbox("Select State Name", states, index=default_idx)

    date = st.date_input("Select Observation Date")
    
    # Layer Display Customization Controls
    st.markdown("---")
    st.markdown("### 🎨 Visual Layer Controls")
    layer_opacity = st.slider("Flood Mask Opacity", min_value=0.1, max_value=1.0, value=0.7, step=0.05)

    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

    st.markdown("---")
    if st.button("🔄 Reset System", use_container_width=True):
        st.session_state.result = None
        st.rerun()

    # Expandable Methodology Drawer
    with st.expander("ℹ️ Data & Methodology Notes"):
        st.markdown("""
        **Data Processing Pipeline:**
        * **Sensor:** Sentinel-1 Synthetic Aperture Radar (SAR) Ground Range Detected (GRD).
        * **Polarization:** Dual-Pol VV & VH mode for water surface contrast.
        * **Speckle Filter:** Refined Lee Speckle Filter to remove granular radar noise.
        * **Dem Masking:** HydroSHEDS DEM slope masking (>5%) applied to eliminate terrain shadows.
        * **Thresholding:** OTSU Automated Thresholding on backscatter coefficients.
        """)

# =========================================================
# RUN ANALYSIS
# =========================================================
if run_btn:
    with st.spinner("Processing Dual-Pol (VV+VH) SAR Imagery & Filtering Noise..."):
        try:
            st.session_state.result = fm.get_flood_map(name, str(date), mode)
        except Exception as e:
            st.error(f"Analysis Execution Failed: {e}")

# =========================================================
# MAIN DISPLAY AREA
# =========================================================

# DEFAULT VIEW: DIRECT FULL-FRAME MAP DISPLAY
if st.session_state.result is None:
    default_m = fm.get_default_india_map()
    map_html = f"<div style='height:620px; overflow:hidden; border-radius:8px;'>{default_m._repr_html_()}</div>"
    st.components.v1.html(map_html, height=620, scrolling=False)

# VIEW AFTER ANALYSIS EXECUTION
else:
    (m, area, flood, water, region, actual) = st.session_state.result

    if actual == "No Data":
        st.error("⚠️ No Sentinel-1 SAR acquisition available within 15 days of target date.")
    else:
        # Severity Categorization
        if area < 1000:
            severity_label = "🟢 Low Inundation"
        elif area < 5000:
            severity_label = "🟡 Moderate Alert"
        elif area < 15000:
            severity_label = "🟠 High Inundation"
        else:
            severity_label = "🔴 Severe Flood Level"

        # KPI Command Dashboard Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Region Analyzed</div>
                    <div class="metric-value">{name.upper()}</div>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Acquisition Date</div>
                    <div class="metric-value">{actual}</div>
                </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Inundated Area</div>
                    <div class="metric-value">{round(area, 2):,} ha</div>
                </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Impact Assessment</div>
                    <div class="metric-value" style="font-size: 15px;">{severity_label}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Map & Action Panel Workspace
        map_col, action_col = st.columns([3.2, 1.2])

        with map_col:
            map_html = f"<div style='height:620px; overflow:hidden; border-radius:8px;'>{m._repr_html_()}</div>"
            st.components.v1.html(map_html, height=620, scrolling=False)

        with action_col:
            tab1, tab2 = st.tabs(["📄 Export Reports", "🌐 GIS Spatial Data"])

            # TAB 1: PDF REPORTS
            with tab1:
                st.write("**Cartographic & Executive Reports**")
                
                if st.button("🗺️ Generate Map PDF", use_container_width=True):
                    with st.spinner("Rendering Cartographic Map PDF..."):
                        try:
                            map_pdf = fm.generate_map_pdf(flood, water, region, name, actual)
                            with open(map_pdf, "rb") as f:
                                st.download_button(
                                    "💾 Download Map PDF",
                                    f,
                                    file_name=map_pdf,
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Map PDF Error: {e}")

                st.write("")

                if st.button("📋 Generate Report PDF", use_container_width=True):
                    with st.spinner("Building Executive Summary Report..."):
                        try:
                            report_pdf = fm.generate_report_pdf(
                                flood, water, region, name, str(date), actual, area, mode
                            )
                            with open(report_pdf, "rb") as f:
                                st.download_button(
                                    "💾 Download Report PDF",
                                    f,
                                    file_name=report_pdf,
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Report Error: {e}")

            # TAB 2: GIS EXPORTS & BACKEND DRIVE SYNC
            with tab2:
                st.write("**Direct GIS Downloads**")
                
                if st.button("📡 Direct GeoTIFF (.tif)", use_container_width=True):
                    with st.spinner("Preparing GeoTIFF..."):
                        try:
                            tif_url = fm.get_flood_raster_url(flood, region, name, mode=mode)
                            st.success("GeoTIFF Ready!")
                            st.markdown(f"[👉 **Download GeoTIFF (.tif)**]({tif_url})")
                        except Exception as e:
                            st.error(f"GeoTIFF Export Failed: {e}")

                st.write("")

                if st.button("🔷 Direct GeoJSON Vectors", use_container_width=True):
                    with st.spinner("Converting raster mask to vector..."):
                        try:
                            geojson_url = fm.get_flood_geojson_url(flood, region, name)
                            st.success("GeoJSON Layer Ready!")
                            st.markdown(f"[👉 **Download GeoJSON (.json)**]({geojson_url})")
                        except Exception as e:
                            st.error(f"GeoJSON Export Failed: {e}")

                st.markdown("---")
                st.write("**Full 10m Native Cloud-to-Local Downloader**")

                local_dir = st.text_input("Local Target Directory Path:", value="./downloads")
                layer_type = st.radio("Export Format:", ["Raster (.tif)", "Shapefile (.shp)"])

                if st.button("💾 Pipeline: GEE ➔ Drive ➔ Local", use_container_width=True):
                    fmt_key = "raster" if "Raster" in layer_type else "vector"
                    
                    with st.spinner("Initiating 10m Cloud Engine Task..."):
                        try:
                            task_id = fm.trigger_drive_export_10m(flood, region, name, export_type=fmt_key)
                            st.info(f"Task Submitted (ID: `{task_id}`). Waiting for completion...")
                            
                            status_box = st.empty()
                            while True:
                                status = fm.check_task_status(task_id)
                                status_box.write(f"🔄 Engine Task Status: **{status}**")
                                
                                if status == "COMPLETED":
                                    status_box.success("GEE Processing Complete!")
                                    break
                                elif status in ["FAILED", "CANCELLED"]:
                                    status_box.error("GEE Export Task Failed.")
                                    break
                                
                                time.sleep(10)

                            if status == "COMPLETED":
                                with st.spinner(f"Syncing from Drive to `{local_dir}`..."):
                                    prefix = f"{name}_flood_10m"
                                    saved_path = fm.sync_drive_to_local_path(prefix, local_dir)
                                    if saved_path:
                                        st.success(f"🎉 Saved locally to: `{saved_path}`")
                                    else:
                                        st.error("File sync failed. Verify Google Drive credentials.")
                        except Exception as e:
                            st.error(f"Pipeline Execution Failed: {e}")

# =========================================================
# APPLICATION FOOTER
# =========================================================
st.markdown("""
    <div style="
        margin-top: 30px;
        padding: 12px;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-top: 2px solid #334155;
        border-radius: 8px;
        text-align: center;
        color: #94a3b8;
        font-family: 'Inter', sans-serif;
        font-size: 12px;
    ">
        <p style="margin: 0; font-weight: 600; color: #e2e8f0;">
            🌊  Advanced Flood Mapping System
        </p>
        <p style="margin: 4px 0 0 0; font-size: 11px; color: #38bdf8;">
            Designed & Developed by <b>Naveen Bussari</b> | 📧 <a href="mailto:bussarinaveen18@gmail.com" style="color: #38bdf8; text-decoration: none;">bussarinaveen18@gmail.com</a>
        </p>
    </div>
""", unsafe_allow_html=True)