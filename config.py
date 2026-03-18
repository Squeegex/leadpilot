# ============================================
# LeadPilot Configuration
# IMPORTANT: In production, use environment variables instead of this file
# ============================================

import os

class Config:
    # --- Supabase (Database) ---
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qxfxpkrzxbnnzepwxsmo.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4Znhwa3J6eGJubnplcHd4c21vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzc0NTcsImV4cCI6MjA4OTM1MzQ1N30.OVR2EgCaqiVUJLm6JGD6ddQic79UF46vtzW7pj_XSS4")
    
    # --- RentCast (Property Data) ---
    RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "8aad11c2e0004904a619ff77bef0f56c")
    RENTCAST_BASE_URL = "https://api.rentcast.io/v1"
    
    # --- Emailable (Email Verification) ---
    EMAILABLE_API_KEY = os.getenv("EMAILABLE_API_KEY", "live_c12003cf380ca14c4559")
    EMAILABLE_BASE_URL = "https://api.emailable.com/v1"
    
    # --- NumVerify (Phone Verification) ---
    NUMVERIFY_API_KEY = os.getenv("NUMVERIFY_API_KEY", "d5ffebfd08ee9f975fcd33ff58f8028e")
    NUMVERIFY_BASE_URL = "http://apilayer.net/api"
    
    # --- Anthropic Claude (AI Messages) ---
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")  # Will need to add this
    
    # --- LeadPilot Settings ---
    TARGET_ZIPS = ["92014", "92037", "92103", "92104", "92106", "92107", "92109", "92127"]
    SERVICES = ["window_cleaning", "solar_panel_cleaning", "pressure_washing", "gutter_cleaning"]
    METRO_AREA = "San Diego"
    STATE = "CA"
    MAX_LEADS_PER_DAY = 10
    MIN_LEAD_SCORE = 60
    VERIFIED_MIN_SCORE = 75  # Minimum score for verified tab
    
    # --- Service Display Names ---
    SERVICE_NAMES = {
        "window_cleaning": "Window Cleaning",
        "solar_panel_cleaning": "Solar Panel Cleaning",
        "pressure_washing": "Pressure Washing",
        "gutter_cleaning": "Gutter Cleaning",
    }
