# app.py
import os
from math import radians, cos, sin, asin, sqrt

import requests
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

import openai
import openrouteservice

# --- CONFIG / KEYS ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENTRIPMAP_KEY = os.getenv("OPENTRIPMAP_KEY")
ORS_API_KEY = os.getenv("ORS_API_KEY")
openai.api_key = OPENAI_API_KEY
ors_client = openrouteservice.Client(key=ORS_API_KEY) if ORS_API_KEY else None

# --- CHECK KEYS ---
missing = [k for k, v in {"OpenAI": OPENAI_API_KEY, "OpenTripMap": OPENTRIPMAP_KEY}.items() if not v]
if missing:
    st.error(f"⚠️ Missing API keys: {', '.join(missing)} in .env")

# --- INTEREST MAPPING ---
INTEREST_MAPPING = {
    "museums": "cultural",
    "historic": "historic",
    "nature": "natural",
    "food": "restaurants,cafes",
    "nightlife": "nightlife",
    "shopping": "shops"
}

# --- HELPERS ---
@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    geolocator = Nominatim(user_agent="student_travel_planner")
    loc = geolocator.geocode(place_name, timeout=10)
    if not loc:
        return None
    return {"lat": loc.latitude, "lon": loc.longitude, "display_name": loc.address}

@st.cache_data(show_spinner=False)
def fetch_pois_opentripmap(lat, lon, radius_m=5000, kinds=None, limit=50):
    url = "https://api.opentripmap.com/0.1/en/places/radius"
    params = {
        "apikey": OPENTRIPMAP_KEY,
        "radius": radius_m,
        "lon": lon,
        "lat": lat,
        "limit": limit,
        "format": "json"
    }
    if kinds:
        params["kinds"] = kinds
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json()
        return items
    except requests.HTTPError as e:
        st.error(f"Error fetching POIs: {e}")
        return []

@st.cache_data(show_spinner=False)
def get_poi_details(xid):
    url = f"https://api.opentripmap.com/0.1/en/places/xid/{xid}"
    try:
        resp = requests.get(url, params={"apikey": OPENTRIPMAP_KEY}, timeout=10)
        if resp.status_code != 200:
            return {}
        return resp.json()
    except:
        return {}

def haversine_km(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(min(1, sqrt(a)))
    km = 6371 * c
    return km

def travel_time_between(lat1, lon1, lat2, lon2, mode="foot"):
    # Use OSRM public demo by default to avoid ORS rate limits
    profile = "foot" if mode == "foot" else "driving"
    coords = f"{lon1},{lat1};{lon2},{lat2}"
    try:
        r = requests.get(
            f"http://router.project-osrm.org/route/v1/{profile}/{coords}?overview=false",
            timeout=8
        )
        return r.json()["routes"][0]["duration"] / 60
    except Exception:
        # fallback estimate: walking 5 km/h, driving 40 km/h
        dist = haversine_km(lat1, lon1, lat2, lon2)
        speed = 5.0 if mode == "foot" else 40.0
        return (dist / speed) * 60


def score_poi(poi, origin_lat, origin_lon):
    lat = poi.get("point", {}).get("lat") or poi.get("lat")
    lon = poi.get("point", {}).get("lon") or poi.get("lon")
    if lat is None or lon is None:
        return 0
    dist_km = haversine_km(origin_lat, origin_lon, lat, lon)
    popularity = poi.get("rate", 0)
    return (popularity * 2) - dist_km

def build_greedy_itinerary(pois, start_lat, start_lon, days=1, hours_per_day=8, mode="foot"):
    current_lat, current_lon = start_lat, start_lon
    poi_list = []
    for p in pois:
        lat = p.get("point", {}).get("lat") or p.get("lat")
        lon = p.get("point", {}).get("lon") or p.get("lon")
        if lat is None or lon is None:
            continue
        p["_lat"], p["_lon"] = lat, lon
        p["_score"] = score_poi(p, start_lat, start_lon)
        poi_list.append(p)
    poi_list = sorted(poi_list, key=lambda x: -x["_score"])
    day = 1
    itinerary = {"days": []}
    current_day = {"day": day, "items": [], "minutes_left": hours_per_day*60}
    for p in poi_list:
        travel_min = travel_time_between(current_lat, current_lon, p["_lat"], p["_lon"], mode=mode)
        visit_min = 60
        total_needed = travel_min + visit_min
        if current_day["minutes_left"] >= total_needed:
            current_day["items"].append({
                "name": p.get("name"),
                "lat": p["_lat"],
                "lon": p["_lon"],
                "travel_min": round(travel_min,1),
                "visit_min": visit_min,
                "desc": p.get("kinds")
            })
            current_day["minutes_left"] -= total_needed
            current_lat, current_lon = p["_lat"], p["_lon"]
        else:
            itinerary["days"].append(current_day)
            day += 1
            if day > days:
                break
            current_day = {"day": day, "items": [], "minutes_left": hours_per_day*60}
            travel_min = travel_time_between(start_lat, start_lon, p["_lat"], p["_lon"], mode=mode)
            if current_day["minutes_left"] >= (travel_min + visit_min):
                current_day["items"].append({
                    "name": p.get("name"),
                    "lat": p["_lat"],
                    "lon": p["_lon"],
                    "travel_min": round(travel_min,1),
                    "visit_min": visit_min,
                    "desc": p.get("kinds")
                })
                current_day["minutes_left"] -= (travel_min + visit_min)
                current_lat, current_lon = p["_lat"], p["_lon"]
    if current_day["items"]:
        itinerary["days"].append(current_day)
    return itinerary

def generate_llm_itinerary(itinerary, destination, budget_estimate):
    prompt = f"""You are a helpful travel planner writing a student-friendly, budget-conscious itinerary.
Destination: {destination}
Estimated budget: {budget_estimate}
Itinerary data:
{itinerary}

Write a clear day-by-day plan with:
- short morning/afternoon/evening suggestions,
- quick budget tips (cheap eats, student discounts ideas),
- travel time notes and simple cost estimates per day.
Keep it concise and friendly.
"""
    try:
        res = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content": prompt}],
            temperature=0.6,
            max_tokens=500
        )
        return res.choices[0].message.content
    except Exception as e:
        return "LLM generation failed: " + str(e)


# --- STREAMLIT UI ---
st.set_page_config(page_title="AI Travel Planner", layout="wide")
st.title("AI Travel Planner — Student Edition ✈️🎒")

# Initialize session_state keys if they don't exist
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "lat" not in st.session_state:
    st.session_state.lat = None
if "lon" not in st.session_state:
    st.session_state.lon = None
if "llm_text" not in st.session_state:
    st.session_state.llm_text = None

with st.sidebar:
    st.header("Plan inputs")
    destination = st.text_input("Destination", value="Jaipur, India")
    days = st.number_input("Days to plan", 1, 14, 2)
    hours_per_day = st.number_input("Hours sightseeing/day", 2, 12, 7)
    radius_km = st.slider("Search radius (km)", 1, 20, 5)
    interests = st.multiselect(
        "Interests",
        ["museums","historic","nature","food","nightlife","shopping"],
        default=["historic","food"]
    )
    budget = st.number_input("Total budget", 0, value=5000)
    mode = st.selectbox("Travel mode", ["foot","driving"], index=0)

col1, col2 = st.columns([1,2])
with col1:
    if st.button("Generate plan"):
        with st.spinner("Geocoding destination..."):
            loc = geocode_place(destination)
        if not loc:
            st.error("Could not geocode destination.")
        else:
            st.success(f"Found: {loc['display_name']}")
            st.session_state.lat = loc["lat"]
            st.session_state.lon = loc["lon"]
            st.info("Fetching POIs...")
            kinds = ",".join(INTEREST_MAPPING[i] for i in interests) if interests else None
            raw_pois = fetch_pois_opentripmap(
                st.session_state.lat, st.session_state.lon,
                radius_m=radius_km*1000, kinds=kinds, limit=60
            )
            if not raw_pois:
                st.warning("No POIs found. Try increasing radius or changing interests.")
            else:
                st.success(f"Found {len(raw_pois)} POIs — building itinerary...")
                st.session_state.itinerary = build_greedy_itinerary(
                    raw_pois, st.session_state.lat, st.session_state.lon, days, hours_per_day, mode
                )
                st.session_state.llm_text = generate_llm_itinerary(
                    st.session_state.itinerary, destination, budget
                )

    # --- Display outputs outside button ---
    if st.session_state.itinerary:
        st.markdown("### AI-generated itinerary")
        st.write(st.session_state.llm_text)
        st.download_button(
            "Download itinerary (JSON)",
            data=pd.json_normalize(st.session_state.itinerary).to_json(orient="records"),
            file_name="itinerary.json"
        )

with col2:
    st.markdown("### Map preview")
    if st.session_state.itinerary and st.session_state.lat and st.session_state.lon:
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=13)
        for day in st.session_state.itinerary.get("days", []):
            for item in day["items"]:
                folium.Marker(
                    [item["lat"], item["lon"]],
                    popup=f"{item['name']} (Day {day['day']}) - {item['travel_min']} min travel",
                    tooltip=item['name']
                ).add_to(m)
        st_folium(m, width=700, height=500)
    else:
        st.info("Generate your itinerary first to see it on the map.")

