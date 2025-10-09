# 🌍 AI Travel Planner — Student Edition ✈️🎒

An intelligent **AI-powered travel itinerary generator** built with **Streamlit**, **OpenTripMap API**, and **LLM-based recommendations**.  
Plan your perfect trip easily — just enter your destination, duration, interests, and budget, and let AI handle the rest!

---

## 🚀 Features

✅ **Automatic Destination Geocoding** — Enter any place name, and the app finds it using OpenStreetMap.  
✅ **POI Discovery** — Fetches attractions, landmarks, and restaurants from **OpenTripMap API**.  
✅ **Smart Itinerary Builder** — Greedy algorithm optimizes sightseeing routes by day.  
✅ **AI-Generated Itinerary** — Natural-language trip summary using an LLM (like OpenAI or Gemini).  
✅ **Interactive Map Preview** — View all attractions on a map powered by **Folium**.  
✅ **Downloadable Plans** — Export your itinerary in JSON format.

---

## 🧠 Tech Stack

- **Frontend/UI:** [Streamlit](https://streamlit.io/)
- **Mapping & Geocoding:** [OpenStreetMap](https://www.openstreetmap.org/) + [OpenTripMap API](https://opentripmap.io/)
- **AI Generation:** OpenAI / Gemini / LLM-based text generation
- **Visualization:** [Folium](https://python-visualization.github.io/folium/)
- **Data Processing:** pandas, requests

---

## ⚙️ Installation & Setup Guide

Follow these steps to install and run the project on your local machine 👇

### 🪜 Step 1: Clone the Repository
Open your terminal or command prompt and run:

```bash
git clone https://github.com/avro000/ai-trip-planner.git
cd ai-travel-planner
```

### 🪜 Step 2: Create a Virtual Environment

Windows
```bash
python -m venv venv
venv\Scripts\activate
```

macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 🪜 Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 🪜 Step 4: Run the Application
```bash
streamlit run app.py
```
### Live Demo
---

Click the link- https://ai-travel-planner-tgcuzci2342j8fdxnoxux5.streamlit.app/
