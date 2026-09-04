# =========================================================
# modules/flood_module.py
# =========================================================

import os
import json
import ee
import folium
import requests
import streamlit as st

from google.oauth2 import service_account
from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from geopy.distance import geodesic

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.lib.enums import (
    TA_CENTER,
    TA_JUSTIFY
)

# Optional Gemini AI SDK integration
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# Optional dependencies for Drive API Local Sync
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from google.oauth2.credentials import Credentials
    HAS_DRIVE_API = True
except ImportError:
    HAS_DRIVE_API = False

# =========================================================
# INIT EARTH ENGINE
# =========================================================
def init_ee():
    """Initializes Earth Engine safely without accessing private internals."""
    try:
        ee.Number(1).getInfo()
        return
    except Exception:
        pass

    try:
        if "gcp_service_account" in st.secrets:
            secret_val = st.secrets["gcp_service_account"]
            
            if isinstance(secret_val, str):
                creds_dict = json.loads(secret_val)
            else:
                creds_dict = dict(secret_val)

            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')

            scopes = ['https://www.googleapis.com/auth/earthengine']
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=scopes
            )
            
            ee.Initialize(
                credentials=credentials,
                project='rare-host-474609-d8'
            )
        else:
            ee.Initialize(project='rare-host-474609-d8')
    except Exception as e:
        st.error(f"Earth Engine Initialization Failed: {e}")
        st.stop()

# =========================================================
# FETCH ADMIN DISTRICT & STATE LISTS FOR DROPDOWN
# =========================================================
@st.cache_data
def get_admin_lists():
    """Queries GEE asset to retrieve sorted lists of unique districts and states."""
    init_ee()
    fc = ee.FeatureCollection(
        "projects/rare-host-474609-d8/assets/INDIA_DIST_BDY__UPDATED__2023_LCC"
    )
    
    try:
        districts = sorted(fc.aggregate_array("District").distinct().getInfo())
        states = sorted(fc.aggregate_array("STATE").distinct().getInfo())
        return districts, states
    except Exception:
        return ["FARRUKHABAD", "CACHAR"], ["UTTAR PRADESH", "ASSAM"]

# =========================================================
# DEFAULT INDIA MAP (FULL-FRAME PERFECT FIT FOR ALL STATES)
# =========================================================
def get_default_india_map():
    init_ee()
    
    m = folium.Map(
        location=[20.2, 78.5],
        zoom_start=4.6,
        tiles="OpenStreetMap",
        control_scale=True
    )

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite Imagery',
        overlay=False
    ).add_to(m)

    all_districts = ee.FeatureCollection(
        "projects/rare-host-474609-d8/assets/INDIA_DIST_BDY__UPDATED__2023_LCC"
    )

    unique_states = all_districts.aggregate_array("STATE").distinct()

    def set_state_id(feature):
        state_name = feature.get('STATE')
        state_index = unique_states.indexOf(state_name)
        return feature.set('STATE_NUM_ID', ee.Number(state_index).add(1))

    numbered_districts = all_districts.map(set_state_id)

    state_raster = numbered_districts.reduceToImage(
        properties=['STATE_NUM_ID'],
        reducer=ee.Reducer.first()
    ).unmask(0)

    state_min = state_raster.reduceNeighborhood(
        reducer=ee.Reducer.min(),
        kernel=ee.Kernel.square(radius=1.5, units='pixels')
    )
    state_max = state_raster.reduceNeighborhood(
        reducer=ee.Reducer.max(),
        kernel=ee.Kernel.square(radius=1.5, units='pixels')
    )
    
    complete_state_edges = state_min.neq(state_max).And(state_raster.gt(0).Or(state_max.gt(0)))

    admin_group = folium.FeatureGroup(name="Admin Boundaries", show=True)
    
    state_map = complete_state_edges.selfMask().getMapId({"palette": ["000000"]})
    folium.raster_layers.TileLayer(
        tiles=state_map["tile_fetcher"].url_format,
        attr='Google Earth Engine',
        overlay=True,
        control=False,
        show=True
    ).add_to(admin_group)

    STATE_CENTROIDS = {
        "JAMMU AND KASHMIR": [33.7782, 76.5762],
        "LADAKH": [34.1526, 77.5771],
        "HIMACHAL PRADESH": [31.1048, 77.1734],
        "PUNJAB": [31.1471, 75.3412],
        "UTTARAKHAND": [30.0668, 79.0193],
        "HARYANA": [29.0588, 76.0856],
        "DELHI": [28.7041, 77.1025],
        "RAJASTHAN": [27.0238, 74.2179],
        "UTTAR PRADESH": [26.8467, 80.9462],
        "BIHAR": [25.0961, 85.3131],
        "SIKKIM": [27.5330, 88.5122],
        "ARUNACHAL PRADESH": [28.2180, 94.7278],
        "ASSAM": [26.2006, 92.9376],
        "NAGALAND": [26.1584, 94.5624],
        "MANIPUR": [24.6637, 93.9063],
        "MIZORAM": [23.1645, 92.9376],
        "TRIPURA": [23.9408, 91.9882],
        "MEGHALAYA": [25.4670, 91.3662],
        "WEST BENGAL": [22.9868, 87.8550],
        "JHARKHAND": [23.6102, 85.2799],
        "ODISHA": [20.9517, 85.0985],
        "CHHATTISGARH": [21.2787, 81.8661],
        "MADHYA PRADESH": [22.9734, 78.6569],
        "GUJARAT": [22.2587, 71.1924],
        "MAHARASHTRA": [19.7515, 75.7139],
        "TELANGANA": [18.1124, 79.0193],
        "ANDHRA PRADESH": [15.9129, 79.7400],
        "KARNATAKA": [15.3173, 75.7139],
        "GOA": [15.2993, 74.1240],
        "KERALA": [10.8505, 76.2711],
        "TAMIL NADU": [11.1271, 78.6569],
        "PUDUCHERRY": [11.9416, 79.8083],
    }

    for state_name, coords in STATE_CENTROIDS.items():
        icon = folium.DivIcon(
            icon_size=(150, 36),
            icon_anchor=(75, 18),
            html=f'''
                <div style="
                    font-family: Arial, sans-serif;
                    font-size: 10px;
                    font-weight: bold;
                    color: #ffffff;
                    text-shadow: -1px -1px 2px #000, 1px -1px 2px #000, -1px 1px 2px #000, 1px 1px 2px #000;
                    white-space: nowrap;
                    text-align: center;
                    pointer-events: none;
                ">
                    {state_name}
                </div>
            '''
        )
        folium.Marker(
            location=coords,
            icon=icon
        ).add_to(admin_group)

    admin_group.add_to(m)
    folium.LayerControl(collapsed=False, position='topright').add_to(m)
    
    return m

# =========================================================
# GET REGION
# =========================================================
def get_region(name, mode):
    fc = ee.FeatureCollection(
        "projects/rare-host-474609-d8/assets/INDIA_DIST_BDY__UPDATED__2023_LCC"
    )

    if mode == "district":
        filtered = fc.filter(ee.Filter.eq("District", name.upper()))
        geom = filtered.geometry()
    else:
        filtered = fc.filter(ee.Filter.eq("STATE", name.upper()))
        geom = filtered.geometry().dissolve().simplify(maxError=500)

    return geom

def _date_to_string(user_date):
    """Normalize Streamlit/date/datetime input to YYYY-MM-DD."""
    if isinstance(user_date, datetime):
        return user_date.strftime("%Y-%m-%d")
    try:
        return user_date.strftime("%Y-%m-%d")
    except Exception:
        return str(user_date)

def _image_metadata(img, requested_date):
    """Return a client-side metadata dictionary for a Sentinel-1 image."""
    props = img.toDictionary([
        "system:index",
        "system:time_start",
        "platform_number",
        "orbitProperties_pass",
        "orbitNumber_start",
        "relativeOrbitNumber_start",
        "instrumentMode",
        "resolution_meters",
        "transmitterReceiverPolarisation"
    ]).getInfo()

    ts = props.get("system:time_start")
    acquired = datetime.utcfromtimestamp(ts / 1000.0) if ts else None
    acquired_date = acquired.strftime("%Y-%m-%d") if acquired else "Unknown"
    acquired_time = acquired.strftime("%H:%M:%S UTC") if acquired else "Unknown"

    req = datetime.strptime(requested_date, "%Y-%m-%d").date()
    act = datetime.strptime(acquired_date, "%Y-%m-%d").date() if acquired else req
    gap_days = (req - act).days

    return {
        "requested_date": requested_date,
        "actual_date": acquired_date,
        "acquisition_time": acquired_time,
        "satellite": f"Sentinel-1{props.get('platform_number', 'Unknown')}",
        "platform": props.get("platform_number", "Unknown"),
        "orbit_direction": props.get("orbitProperties_pass", "Unknown"),
        "absolute_orbit": props.get("orbitNumber_start", "Unknown"),
        "relative_orbit": props.get("relativeOrbitNumber_start", "Unknown"),
        "instrument_mode": props.get("instrumentMode", "Unknown"),
        "polarization": props.get("transmitterReceiverPolarisation", []),
        "product_id": props.get("system:index", "Unknown"),
        "gap_days": gap_days
    }

def find_latest_sar_image(region, user_date, fallback_days=30):
    """
    Priority:
    1. Find an image acquired on the exact requested date.
    2. If unavailable, find the latest earlier image within fallback_days.
    3. Never silently label an older image as the requested date.
    """
    target_str = _date_to_string(user_date)
    target_dt = datetime.strptime(target_str, "%Y-%m-%d")
    next_dt = target_dt + timedelta(days=1)
    fallback_start = target_dt - timedelta(days=fallback_days)

    base = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )

    try:
        exact = (
            base.filterDate(
                target_dt.strftime("%Y-%m-%d"),
                next_dt.strftime("%Y-%m-%d")
            )
            .sort("system:time_start", False)
        )

        exact_count = exact.size().getInfo()
        if exact_count > 0:
            img = ee.Image(exact.first())
            meta = _image_metadata(img, target_str)
            meta["status"] = "EXACT_DATE_AVAILABLE"
            meta["message"] = "Exact requested-date Sentinel-1 image is available in Google Earth Engine."
            return img, meta

        fallback = (
            base.filterDate(
                fallback_start.strftime("%Y-%m-%d"),
                target_dt.strftime("%Y-%m-%d")
            )
            .sort("system:time_start", False)
        )

        fallback_count = fallback.size().getInfo()
        if fallback_count == 0:
            return None, {
                "status": "NO_GEE_DATA",
                "requested_date": target_str,
                "actual_date": None,
                "gap_days": None,
                "message": (
                    "No Sentinel-1 VV+VH IW image was found in Google Earth Engine "
                    f"for the requested date or previous {fallback_days} days."
                )
            }

        img = ee.Image(fallback.first())
        meta = _image_metadata(img, target_str)
        meta["status"] = "OLDER_IMAGE_ONLY"
        meta["message"] = (
            "The requested-date image is not available in Google Earth Engine. "
            "An earlier image is being reported explicitly as a fallback."
        )
        return img, meta

    except Exception as e:
        return None, {
            "status": "ERROR",
            "requested_date": target_str,
            "actual_date": None,
            "gap_days": None,
            "message": f"Sentinel-1 query failed: {e}"
        }

# =========================================================
# PERMANENT WATER
# =========================================================
def get_permanent_water(region):
    water = ee.Image(
        'projects/rare-host-474609-d8/assets/India_VV_Water_Optimized'
    )
    return water.clip(region).gt(0)

# =========================================================
# DUAL-POL CURRENT WATER EXTRACTION
# =========================================================
def get_water(img):
    vv = img.select('VV')
    vh = img.select('VH')

    vv_filtered = vv.focal_median(30, 'circle', 'meters')
    vh_filtered = vh.focal_median(30, 'circle', 'meters')

    open_water_vv = vv_filtered.lt(-17.5)
    open_water_vh = vh_filtered.lt(-24.0)
    
    water_mask = open_water_vv.And(open_water_vh)

    dem = ee.Image('USGS/SRTMGL1_003')
    slope = ee.Terrain.slope(dem)
    water_mask = water_mask.updateMask(slope.lt(3))

    pixel_count = water_mask.connectedPixelCount(maxSize=100, eightConnected=True)
    water_mask = water_mask.updateMask(pixel_count.gte(10))

    return water_mask

# =========================================================
# GEOTIFF RASTER EXPORT FUNCTION
# =========================================================
def get_flood_raster_url(flood, region, name, mode="district"):
    export_scale = 30 if mode == "district" else 100
    simple_geom = region.simplify(maxError=500)
    export_image = flood.unmask(0).byte()

    return export_image.getDownloadURL({
        'name': f"{name}_flood_{mode}_{export_scale}m",
        'scale': export_scale,
        'crs': 'EPSG:4326',
        'region': simple_geom,
        'format': 'GEO_TIFF'
    })

# =========================================================
# GEOJSON VECTOR EXPORT FUNCTION
# =========================================================
def get_flood_geojson_url(flood, region, name):
    vectors = flood.reduceToVectors(
        geometry=region,
        scale=30,
        geometryType='polygon',
        eightConnected=False,
        maxPixels=1e13
    )
    return vectors.getDownloadURL(filetype="GEO_JSON", filename=f"{name}_flood_vectors")

# =========================================================
# DRIVE PIPELINE EXPORT TRIGGER
# =========================================================
def trigger_drive_export_10m(flood, region, name, export_type="raster"):
    init_ee()
    
    if export_type == "raster":
        task = ee.batch.Export.image.toDrive(
            image=flood.unmask(0).byte(),
            description=f"{name}_Flood_10m_Raster",
            folder='EE_Flood_Exports',
            fileNamePrefix=f"{name}_flood_10m",
            region=region,
            scale=10,
            crs='EPSG:4326',
            maxPixels=1e13
        )
    else:
        vectors = flood.reduceToVectors(
            geometry=region,
            scale=10,
            geometryType='polygon',
            eightConnected=False,
            maxPixels=1e13
        )
        task = ee.batch.Export.table.toDrive(
            collection=vectors,
            description=f"{name}_Flood_10m_Vectors",
            folder='EE_Flood_Exports',
            fileNamePrefix=f"{name}_flood_10m_vectors",
            fileFormat='SHP'
        )
        
    task.start()
    return task.id

# =========================================================
# POLL GEE TASK STATUS
# =========================================================
def check_task_status(task_id):
    tasks = ee.batch.Task.list()
    for t in tasks:
        if t.id == task_id:
            return t.status()['state']
    return "UNKNOWN"

# =========================================================
# DRIVE TO LOCAL SYNC
# =========================================================
def sync_drive_to_local_path(filename_prefix, local_save_directory):
    if not HAS_DRIVE_API:
        raise Exception("google-api-python-client is not installed.")

    if not os.path.exists(local_save_directory):
        os.makedirs(local_save_directory)

    if not os.path.exists('credentials.json'):
        raise Exception("credentials.json missing for Google Drive API authorization.")

    creds = Credentials.from_authorized_user_file('credentials.json')
    service = build('drive', 'v3', credentials=creds)

    query = f"name contains '{filename_prefix}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        return None

    file_id = items[0]['id']
    file_name = items[0]['name']
    local_file_path = os.path.join(local_save_directory, file_name)

    request = service.files().get_media(fileId=file_id)
    with open(local_file_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    return local_file_path

# =========================================================
# SAFE GEE IMAGE
# =========================================================
def safe_gee_image(image, region, palette, dim, min_value=None, max_value=None):
    try:
        vis = {
            "region": region.simplify(maxError=500),
            "dimensions": dim,
            "format": "png"
        }

        if palette:
            vis["palette"] = palette
        if min_value is not None:
            vis["min"] = min_value
        if max_value is not None:
            vis["max"] = max_value

        url = image.getThumbURL(vis)
        response = requests.get(url)

        if response.status_code != 200:
            return None

        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception:
        return None

# =========================================================
# AI FLOOD SITUATION BRIEF GENERATOR
# =========================================================
def get_ai_flood_summary(name, date, area_ha, mode):
    """Generates an executive hydrological summary using Google Gemini AI."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        Act as a senior hydrologist at  India. Provide a concise 2-paragraph situation assessment for:
        - Study Area: {name} ({mode.capitalize()})
        - Satellite Observation Date: {date}
        - Estimated Inundated Area: {area_ha:,.2f} hectares

        Paragraph 1: Executive situation overview mentioning seasonal monsoon patterns, regional river network dynamics (e.g., Ghaghara/Gandak/Ganga tributaries), and inundation extent.
        Paragraph 2: Strategic guidance for State Disaster Management Authorities (SDMA) regarding emergency relief deployment and multi-temporal monitoring.
        Keep the tone professional, cartographic, and technical. Do not use Markdown formatting or bullet points.
        """
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        if response and response.text:
            return response.text.strip()
            
    except Exception as e:
        st.error(f"❌ Gemini API Call Failed: {e}")
        return None

    return None
# =========================================================
# GET FLOOD MAP
# =========================================================
def get_flood_map(name, date, mode):
    init_ee()

    region = get_region(name, mode)
    user_date = datetime.strptime(date, "%Y-%m-%d")
    
    after_img, metadata = find_latest_sar_image(region, user_date)

    if after_img is None:
        return (None, 0, None, None, region, metadata)

    actual = metadata["actual_date"]

    vv = after_img.select('VV')
    vh = after_img.select('VH')
    vv_vh_ratio = vv.subtract(vh).rename('VV_VH_ratio')
    after = after_img.addBands(vv_vh_ratio)

    permanent_water = get_permanent_water(region)
    current_water = get_water(after)

    flood = current_water.And(permanent_water.Not())
    flood = flood.updateMask(flood).clip(region)

    calc_scale = 10 if mode == "district" else 30

    area = flood.multiply(ee.Image.pixelArea()).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=calc_scale,
        maxPixels=1e13,
        bestEffort=True
    )

    area_dict = area.getInfo()
    raw_val = list(area_dict.values())[0] if area_dict else 0
    flood_area = (raw_val / 10000) if raw_val else 0

    bbox = region.bounds().coordinates().getInfo()[0]
    min_lon, min_lat = bbox[0]
    max_lon, max_lat = bbox[2]
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7 if mode == "state" else 9,
        tiles="OpenStreetMap",
        control_scale=True
    )

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite Imagery',
        overlay=False
    ).add_to(m)

    sar_clip = after.select('VV').clip(region)
    sar_map = sar_clip.getMapId({"min": -25, "max": 0})
    folium.raster_layers.TileLayer(
        tiles=sar_map["tile_fetcher"].url_format,
        attr='Google Earth Engine',
        name='SAR VV',
        overlay=True,
        control=True,
        show=False
    ).add_to(m)

    flood_map = flood.selfMask().getMapId({"palette": ["FF0000"]})
    folium.raster_layers.TileLayer(
        tiles=flood_map["tile_fetcher"].url_format,
        attr='Google Earth Engine',
        name='Flood Inundation',
        overlay=True,
        control=True,
        opacity=0.8,
        show=True
    ).add_to(m)

    water_map = permanent_water.selfMask().getMapId({"palette": ["0000FF"]})
    folium.raster_layers.TileLayer(
        tiles=water_map["tile_fetcher"].url_format,
        attr='Google Earth Engine',
        name='Permanent Water',
        overlay=True,
        control=True,
        opacity=0.8,
        show=True
    ).add_to(m)

    all_districts = ee.FeatureCollection(
        "projects/rare-host-474609-d8/assets/INDIA_DIST_BDY__UPDATED__2023_LCC"
    )
    unique_states = all_districts.aggregate_array("STATE").distinct()

    def set_state_id(feature):
        state_name = feature.get('STATE')
        state_index = unique_states.indexOf(state_name)
        return feature.set('STATE_NUM_ID', ee.Number(state_index).add(1))

    numbered_districts = all_districts.map(set_state_id)
    state_image = numbered_districts.reduceToImage(
        properties=['STATE_NUM_ID'],
        reducer=ee.Reducer.first()
    )
    state_edges = state_image.zeroCrossing()

    admin_group = folium.FeatureGroup(name="Admin Boundaries", show=True)
    state_map_id = state_edges.selfMask().getMapId({"palette": ["000000"]})
    folium.raster_layers.TileLayer(
        tiles=state_map_id["tile_fetcher"].url_format,
        attr='Google Earth Engine',
        overlay=True,
        control=False,
        show=True
    ).add_to(admin_group)

    admin_group.add_to(m)

    folium.GeoJson(
        region.simplify(maxError=500).getInfo(),
        style_function=lambda feature: {
            'fillColor': 'none',
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0
        },
        name='Boundary'
    ).add_to(m)

    m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

    folium.LayerControl(collapsed=False, position='topright').add_to(m)

    css = """
    <style>
    .leaflet-control-layers-expanded {
        background: #ffffff !important;
        padding: 10px 14px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
        font-family: Arial, sans-serif !important;
        font-size: 13px !important;
        color: #1e293b !important;
        z-index: 9999 !important;
    }
    </style>
    """
    m.get_root().html.add_child(folium.Element(css))

    return (m, flood_area, flood, permanent_water, region, metadata)

# =========================================================
# GENERATE MAP PDF (SYNCHRONIZED AREA & PIL RESIZING)
# =========================================================
def generate_map_pdf(flood, water, region, name, date, area_ha=None):
    simple_region = region.simplify(maxError=500)
    coords = simple_region.bounds().coordinates().getInfo()[0]
    width = abs(coords[1][0] - coords[0][0])
    dim = 1024 if width < 5 else 512

    # Use precalculated area if passed to avoid numerical mismatch between map and report
    if area_ha is None:
        area_calc = flood.multiply(ee.Image.pixelArea()).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=30,
            maxPixels=1e13,
            bestEffort=True
        )
        area_dict = area_calc.getInfo()
        raw_val = list(area_dict.values())[0] if area_dict else 0
        flood_area = (raw_val / 10000) if raw_val else 0
    else:
        flood_area = area_ha

    user_d = datetime.strptime(date, "%Y-%m-%d")
    sar_img_obj, sar_metadata = find_latest_sar_image(simple_region, user_d)

    if sar_img_obj is None:
        message = (
            sar_metadata.get("message", "SAR image generation failed")
            if isinstance(sar_metadata, dict)
            else "SAR image generation failed"
        )
        raise Exception(message)

    actual_date = (
        sar_metadata.get("actual_date", date)
        if isinstance(sar_metadata, dict)
        else date
    )

    sar = sar_img_obj.select("VV")

    sar_img = safe_gee_image(
        sar.clip(simple_region), simple_region, None, dim, -25, 0
    )
    water_img = safe_gee_image(
        water.selfMask(), simple_region, ["0000FF"], dim
    )
    flood_img = safe_gee_image(
        flood.selfMask(), simple_region, ["FF0000"], dim
    )

    boundary = (
        ee.Image()
        .byte()
        .paint(
            featureCollection=ee.FeatureCollection(simple_region),
            color=1,
            width=3
        )
    )
    boundary_img = safe_gee_image(
        boundary.selfMask(), simple_region, ["000000"], dim
    )

    if sar_img is None:
        raise Exception("Could not create Sentinel-1 base image for PDF.")

    base_size = sar_img.size

    def normalize_image(img):
        if img is None:
            return None
        img = img.convert("RGBA")
        if img.size != base_size:
            img = img.resize(base_size, Image.Resampling.LANCZOS)
        return img

    combined = normalize_image(sar_img)
    water_img = normalize_image(water_img)
    flood_img = normalize_image(flood_img)
    boundary_img = normalize_image(boundary_img)

    if water_img is not None:
        combined = Image.alpha_composite(combined, water_img)
    if flood_img is not None:
        combined = Image.alpha_composite(combined, flood_img)
    if boundary_img is not None:
        combined = Image.alpha_composite(combined, boundary_img)

    width_km = geodesic(
        (coords[0][1], coords[0][0]),
        (coords[1][1], coords[1][0])
    ).km

    scale_km = 50 if width_km > 300 else 20 if width_km > 100 else 10

    fig = plt.figure(figsize=(12, 10))

    fig.text(
        0.5, 0.965,
        f"Flood Inundation Map of {name.upper()}",
        ha="center",
        fontsize=22,
        fontweight="bold",
        color="#0B4FA2"
    )

    fig.text(
        0.5, 0.935,
        f"Derived from Sentinel-1 Dual-Pol SAR Imagery ({actual_date})",
        ha="center",
        fontsize=11,
        color="darkred"
    )

    ax = fig.add_axes([0.05, 0.12, 0.70, 0.78])
    ax.imshow(combined)
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.5)
        spine.set_color("black")

    legend_ax = fig.add_axes([0.77, 0.55, 0.20, 0.18])
    legend_ax.axis("off")

    flood_patch = mpatches.Patch(
        color="red", label="Flood Inundation"
    )
    water_patch = mpatches.Patch(
        color="blue", label="Permanent Water"
    )
    boundary_patch = mpatches.Patch(
        color="black", label="Boundary"
    )

    legend_ax.legend(
        handles=[flood_patch, water_patch, boundary_patch],
        loc="center",
        fontsize=10,
        frameon=True
    )

    north_ax = fig.add_axes([0.83, 0.80, 0.08, 0.10])
    north_ax.axis("off")
    north_ax.annotate(
        "N",
        xy=(0.5, 0.9),
        xytext=(0.5, 0.2),
        arrowprops=dict(
            facecolor="black",
            width=3,
            headwidth=10
        ),
        ha="center",
        fontsize=14,
        fontweight="bold"
    )

    info_text = (
        f"Requested Date: {date}\n\n"
        f"Satellite Date: {actual_date}\n\n"
        f"Estimated Flood:\n{round(flood_area, 2):,} ha\n\n"
        f"Sensor:\nSentinel-1 (VV+VH)"
    )

    fig.text(
        0.78, 0.32,
        info_text,
        fontsize=9.5,
        bbox=dict(
            facecolor="#f8f9fa",
            edgecolor="black",
            boxstyle="round,pad=0.5"
        )
    )

    scale_ax = fig.add_axes([0.78, 0.16, 0.18, 0.05])
    scale_ax.set_xlim(0, scale_km)
    scale_ax.set_ylim(0, 1)

    scale_ax.plot(
        [0, scale_km], [0.5, 0.5],
        color="black",
        linewidth=2.5
    )

    for x in [0, scale_km / 2, scale_km]:
        scale_ax.plot(
            [x, x], [0.3, 0.7],
            color="black",
            linewidth=1.5
        )
        scale_ax.text(x, 0.8, f"{int(x)}", ha="center", fontsize=9)

    scale_ax.text(
        scale_km / 2,
        -0.15,
        "Kilometers",
        ha="center",
        fontsize=9.5,
        fontweight="bold"
    )
    scale_ax.axis("off")

    footer = (
        "Source: Sentinel-1 Dual-Pol SAR | "
        "Analysis Engine: Google Earth Engine"
    )
    fig.text(0.05, 0.04, footer, fontsize=8, color="gray")

    output_name = f"{name}_{date}_map.pdf"
    plt.savefig(
        output_name,
        dpi=300,
        bbox_inches="tight",
        format="pdf"
    )
    plt.close(fig)

    return output_name

# =========================================================
# GENERATE REPORT PDF (DYNAMIC AI EXECUTIVE BRIEF)
# =========================================================
def generate_report_pdf(flood, water, region, name, user_date, sat_date, area, mode):
    output_name = f"{name}_{sat_date}_report.pdf"

    doc = SimpleDocTemplate(
        output_name,
        rightMargin=40, leftMargin=40,
        topMargin=35, bottomMargin=35
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('title_style', parent=styles['Title'], alignment=TA_CENTER, fontSize=18, leading=22, spaceAfter=18)
    heading_style = ParagraphStyle('heading_style', parent=styles['Heading2'], fontSize=13, leading=16, textColor=colors.HexColor('#0B4FA2'))
    body_style = ParagraphStyle('body_style', parent=styles['BodyText'], alignment=TA_JUSTIFY, fontSize=10.5, leading=16, spaceAfter=10)
    footer_style = ParagraphStyle('footer_style', parent=styles['BodyText'], alignment=TA_JUSTIFY, fontSize=8.5, leading=12, textColor=colors.grey)

    area_name = f"{name} District" if mode == "district" else f"{name} State"

    # Attempt to generate AI Situation Brief using Gemini AI
    ai_brief = get_ai_flood_summary(name, sat_date, area, mode)
    
    if ai_brief:
        location_text = ai_brief.replace("\n", "<br/><br/>")
    else:
        # Standard fallback narrative
        location_text = f"""
        The flood situation across <b>{area_name}</b> was evaluated using Synthetic Aperture Radar (SAR)
        data from Copernicus Sentinel-1 dual-polarization (VV + VH) collected on <b>{sat_date}</b>.<br/><br/>
        SAR penetrates cloud cover to map standing water. The spatial inundation estimate shows 
        approximately <b>{round(area,2):,} hectares</b> flooded across the region.
        """

    table_data = [
        ["Parameter", "Details"],
        ["Study Area", area_name],
        ["Requested Date", user_date],
        ["Satellite Date", sat_date],
        ["Sensor Type", "Sentinel-1 SAR (VV + VH Dual-Pol)"],
        ["Inundated Area", f"{round(area,2):,} ha"]
    ]

    table = Table(table_data, colWidths=[180, 270])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0B4FA2')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa'))
    ]))

    outlook_text = """
    Satellite monitoring supports emergency planning, damage assessment, and disaster relief logistics.
    Periodic multi-temporal observations track the recession of floodwaters over time.
    """

    footer = "<i>Note: Inundation maps are generated from automated dual-polarization SAR thresholding and speckle filtering.</i>"

    content = [
        Paragraph(f"{area_name} Flood Analysis Report", title_style),
        Spacer(1, 10),
        table,
        Spacer(1, 15),
        Paragraph("Executive Summary", heading_style),
        Spacer(1, 6),
        Paragraph(location_text, body_style),
        Spacer(1, 12),
        Paragraph("Monitoring & Relief Outlook", heading_style),
        Spacer(1, 6),
        Paragraph(outlook_text, body_style),
        Spacer(1, 15),
        Paragraph(footer, footer_style)
    ]

    doc.build(content)
    return output_name
