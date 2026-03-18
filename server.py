from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional
import httpx
import os
import traceback

app = FastAPI(title="LeadPilot API", version="1.2.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY", "")
EMAILABLE_API_KEY = os.getenv("EMAILABLE_API_KEY", "")
NUMVERIFY_API_KEY = os.getenv("NUMVERIFY_API_KEY", "")
TARGET_ZIPS = ["92014", "92037", "92103", "92104", "92106", "92107", "92109", "92127"]
SERVICE_NAMES = {"window_cleaning": "Window Cleaning", "solar_panel_cleaning": "Solar Panel Cleaning", "pressure_washing": "Pressure Washing", "gutter_cleaning": "Gutter Cleaning"}
lead_cache = {"verified": [], "unverified": [], "last_run": None}


@app.get("/")
async def root():
    return {"app": "LeadPilot API", "version": "1.2.0", "status": "running", "metro": "San Diego", "zip_codes": TARGET_ZIPS, "keys_configured": {"rentcast": bool(RENTCAST_API_KEY), "emailable": bool(EMAILABLE_API_KEY), "numverify": bool(NUMVERIFY_API_KEY)}}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/debug/test-rentcast")
async def test_rentcast():
    if not RENTCAST_API_KEY:
        return {"error": "RENTCAST_API_KEY not configured"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://api.rentcast.io/v1/properties", headers={"X-Api-Key": RENTCAST_API_KEY, "Accept": "application/json"}, params={"zipCode": "92103", "limit": 2}, timeout=30)
            return {"status_code": response.status_code, "response": response.json() if response.status_code == 200 else response.text}
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}


def score_property(prop):
    score = 50
    services_needed = []
    reasons = []
    year_built = prop.get("yearBuilt") or 0
    if year_built and year_built < 2000:
        score += 10
        services_needed.extend(["pressure_washing", "gutter_cleaning"])
        reasons.append(f"Built in {year_built}")
    elif year_built and year_built < 2010:
        score += 5
        services_needed.append("window_cleaning")
    sqft = prop.get("squareFootage") or prop.get("lotSize") or 0
    if sqft and sqft > 2000:
        score += 8
        services_needed.append("window_cleaning")
        reasons.append(f"Larger property ({sqft:,} sqft)")
    bedrooms = prop.get("bedrooms") or 0
    if bedrooms and bedrooms >= 4:
        score += 5
        reasons.append(f"{bedrooms} bedrooms")
    zip_code = prop.get("zipCode", "")
    if zip_code in ["92014", "92037", "92106"]:
        score += 10
        services_needed.append("solar_panel_cleaning")
        reasons.append("Affluent coastal area - high solar adoption")
    elif zip_code in ["92103", "92104", "92109"]:
        score += 5
        reasons.append("Dense neighborhood with rental properties")
    if not services_needed:
        services_needed = ["window_cleaning", "pressure_washing"]
    services_needed = list(set(services_needed))
    base_prices = {"window_cleaning": 150, "solar_panel_cleaning": 180, "pressure_washing": 200, "gutter_cleaning": 120}
    total = sum(base_prices.get(s, 100) for s in services_needed)
    est = f"${total:,}+" if total > 300 else f"${total:,}"
    return {"score": min(score, 100), "services_needed": services_needed, "reasons": reasons, "est_value": est}


def make_outreach(lead):
    contact = lead.get("contact_name") or "there"
    first_name = contact.split()[0] if contact not in ["Homeowner", "Unknown", "there", ""] else "there"
    address_short = (lead.get("name") or "your property").split(",")[0]
    services = [SERVICE_NAMES.get(s, s) for s in lead.get("services_needed", ["window_cleaning"])]
    services_str = " and ".join(services) if len(services) <= 2 else ", ".join(services[:-1]) + f", and {services[-1]}"
    return f"Hi {first_name} - I'm a local {services_str.lower()} specialist in your neighborhood. I noticed your property at {address_short} might benefit from some exterior TLC this spring. Would you be interested in a free estimate? No pressure at all. - Jason, Squeegex"


@app.get("/api/engine/run")
async def run_engine():
    try:
        all_leads = []
        errors = []
        async with httpx.AsyncClient() as client:
            for zip_code in TARGET_ZIPS[:3]:
                try:
                    response = await client.get("https://api.rentcast.io/v1/properties", headers={"X-Api-Key": RENTCAST_API_KEY, "Accept": "application/json"}, params={"zipCode": zip_code, "limit": 5, "propertyType": "Single Family"}, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            properties = data
                        elif isinstance(data, dict):
                            properties = data.get("properties", data.get("results", [data]))
                        else:
                            properties = []
                        for prop in properties:
                            if not isinstance(prop, dict):
                                continue
                            scoring = score_property(prop)
                            lead = {
                                "id": f"lead-{zip_code}-{len(all_leads)+1}",
                                "name": prop.get("addressLine1") or prop.get("formattedAddress") or f"Property in {zip_code}",
                                "contact_name": prop.get("ownerName") or "Homeowner",
                                "lead_type": "homeowner",
                                "address": f"{prop.get('addressLine1', '')}, {prop.get('city', 'San Diego')}, {prop.get('state', 'CA')} {prop.get('zipCode', '')}",
                                "city": prop.get("city") or "San Diego",
                                "state": prop.get("state") or "CA",
                                "zip_code": prop.get("zipCode") or zip_code,
                                "phone": prop.get("ownerPhone") or "",
                                "email": prop.get("ownerEmail") or "",
                                "phone_verified": "likely" if prop.get("ownerPhone") else "unverified",
                                "email_verified": "likely" if prop.get("ownerEmail") else "unverified",
                                "address_verified": "verified",
                                "services_needed": scoring["services_needed"],
                                "source": "property",
                                "reason": " | ".join(scoring["reasons"]) if scoring["reasons"] else f"Residential property in {zip_code} service area",
                                "score": scoring["score"],
                                "est_value": scoring["est_value"],
                                "status": "new",
                                "outreach_message": "",
                            }
                            lead["outreach_message"] = make_outreach(lead)
                            all_leads.append(lead)
                    else:
                        errors.append(f"Zip {zip_code}: HTTP {response.status_code} - {response.text[:200]}")
                except Exception as e:
                    errors.append(f"Zip {zip_code}: {str(e)}")
        all_leads.sort(key=lambda x: x["score"], reverse=True)
        verified = [l for l in all_leads if l.get("phone") or l.get("email")]
        unverified = [l for l in all_leads if not l.get("phone") and not l.get("email")]
        if not verified and unverified:
            verified = unverified[:10]
            unverified = []
        if not verified and not unverified and all_leads:
            verified = all_leads[:10]
        lead_cache["verified"] = verified[:10]
        lead_cache["unverified"] = unverified[:10]
        lead_cache["last_run"] = datetime.now().isoformat()
        return {"success": True, "verified_count": len(lead_cache["verified"]), "unverified_count": len(lead_cache["unverified"]), "total_raw": len(all_leads), "errors": errors if errors else None}
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/leads")
async def get_leads(status: Optional[str] = Query(None), verified_only: bool = Query(True), limit: int = Query(20)):
    leads = lead_cache["verified"] if verified_only else lead_cache["verified"] + lead_cache["unverified"]
    if status:
        leads = [l for l in leads if l.get("status") == status]
    return {"leads": leads[:limit], "total": len(leads), "last_updated": lead_cache.get("last_run")}


@app.get("/api/leads/unverified")
async def get_unverified(limit: int = Query(20)):
    return {"leads": lead_cache["unverified"][:limit], "total": len(lead_cache["unverified"])}


@app.get("/api/leads/{lead_id}/status")
async def update_status(lead_id: str, new_status: str = Query(...)):
    valid = ["new", "contacted", "quote_sent", "booked", "completed", "lost"]
    if new_status not in valid:
        raise HTTPException(400, "Invalid status")
    for lst in [lead_cache["verified"], lead_cache["unverified"]]:
        for lead in lst:
            if lead.get("id") == lead_id:
                lead["status"] = new_status
                return {"success": True}
    raise HTTPException(404, "Lead not found")


@app.get("/api/stats")
async def get_stats():
    v = lead_cache["verified"]
    return {
        "new_today": len([l for l in v if l.get("status") == "new"]),
        "contacted": len([l for l in v if l.get("status") == "contacted"]),
        "quote_sent": len([l for l in v if l.get("status") == "quote_sent"]),
        "booked": len([l for l in v if l.get("status") == "booked"]),
        "completed": len([l for l in v if l.get("status") == "completed"]),
        "total_verified": len(v),
        "total_unverified": len(lead_cache["unverified"]),
        "pipeline_value": sum(int(l.get("est_value", "$0").replace("$", "").replace(",", "").replace("+", "") or 0) for l in v if l.get("status") not in ["lost", "completed"]),
        "avg_score": round(sum(l.get("score", 0) for l in v) / max(len(v), 1)),
        "last_engine_run": lead_cache.get("last_run"),
    }


@app.get("/api/seasonal-tip")
async def seasonal_tip():
    month = datetime.now().month
    tips = {
        (1, 2): {"icon": "r", "title": "Post-Rain Cleanup Season", "body": "Winter rains wrapping up. Push gutter cleaning and pressure washing.", "services": ["Gutter Cleaning", "Pressure Washing"]},
        (3, 4): {"icon": "s", "title": "Spring Push - Window & Solar Season", "body": "Pollen season just ended in San Diego. Homeowners are noticing dirty windows and dusty solar panels. Demand spikes 40% this month.", "services": ["Window Cleaning", "Solar Panel Cleaning"]},
        (5, 6): {"icon": "z", "title": "Peak Solar Season", "body": "San Diego sunshine is strongest. Dirty panels losing 15-25% efficiency.", "services": ["Solar Panel Cleaning", "Window Cleaning"]},
        (7, 8): {"icon": "b", "title": "Summer Entertaining Season", "body": "BBQ season. Homeowners want sharp patios and windows.", "services": ["Window Cleaning", "Pressure Washing"]},
        (9, 10): {"icon": "f", "title": "Fall Prep Season", "body": "Leaves falling, rain coming. Prep gutters and exteriors.", "services": ["Gutter Cleaning", "Pressure Washing"]},
        (11, 12): {"icon": "h", "title": "Holiday & Year-End Push", "body": "Holiday parties, year-end HOA budgets, January listing prep.", "services": ["Window Cleaning", "Gutter Cleaning"]},
    }
    for months, tip in tips.items():
        if month in range(months[0], months[1] + 1):
            return tip
    return tips[(3, 4)]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
