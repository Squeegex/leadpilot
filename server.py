"""
LeadPilot — API Server
FastAPI backend that serves lead data to the dashboard.
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional
import asyncio

from config import Config
from lead_engine import LeadEngine

app = FastAPI(title="LeadPilot API", version="1.0.0")

# Allow the frontend dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the engine
engine = LeadEngine()

# In-memory cache for demo (in production, this comes from Supabase)
lead_cache = {"verified": [], "unverified": [], "last_run": None}


@app.get("/")
async def root():
    return {
        "app": "LeadPilot API",
        "version": "1.0.0",
        "status": "running",
        "metro": Config.METRO_AREA,
        "zip_codes": Config.TARGET_ZIPS,
    }


@app.get("/api/leads")
async def get_leads(
    status: Optional[str] = Query(None, description="Filter by pipeline status"),
    verified_only: bool = Query(True, description="Only show verified leads"),
    limit: int = Query(20, description="Max leads to return"),
):
    """Get leads for the dashboard."""
    leads = lead_cache["verified"] if verified_only else lead_cache["verified"] + lead_cache["unverified"]

    if status:
        leads = [l for l in leads if l.get("status") == status]

    return {
        "leads": leads[:limit],
        "total": len(leads),
        "last_updated": lead_cache.get("last_run"),
    }


@app.get("/api/leads/unverified")
async def get_unverified_leads(limit: int = Query(20)):
    """Get unverified leads (the bonus tab)."""
    return {
        "leads": lead_cache["unverified"][:limit],
        "total": len(lead_cache["unverified"]),
    }


@app.patch("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, new_status: str):
    """Update a lead's pipeline status."""
    valid_statuses = ["new", "contacted", "quote_sent", "booked", "completed", "lost"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    # Update in cache
    for lead_list in [lead_cache["verified"], lead_cache["unverified"]]:
        for lead in lead_list:
            if lead.get("id") == lead_id:
                lead["status"] = new_status
                if new_status == "contacted":
                    lead["contacted_date"] = datetime.now().isoformat()
                elif new_status == "booked":
                    lead["booked_date"] = datetime.now().isoformat()
                elif new_status == "completed":
                    lead["completed_date"] = datetime.now().isoformat()
                return {"success": True, "lead_id": lead_id, "new_status": new_status}

    raise HTTPException(status_code=404, detail="Lead not found")


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    all_verified = lead_cache["verified"]
    return {
        "new_today": len([l for l in all_verified if l.get("status") == "new"]),
        "contacted": len([l for l in all_verified if l.get("status") == "contacted"]),
        "quote_sent": len([l for l in all_verified if l.get("status") == "quote_sent"]),
        "booked": len([l for l in all_verified if l.get("status") == "booked"]),
        "completed": len([l for l in all_verified if l.get("status") == "completed"]),
        "total_verified": len(all_verified),
        "total_unverified": len(lead_cache["unverified"]),
        "pipeline_value": sum(
            int(l.get("est_value", "$0").replace("$", "").replace(",", "").replace("+", ""))
            for l in all_verified
            if l.get("status") not in ["lost", "completed"]
        ),
        "avg_score": round(
            sum(l.get("score", 0) for l in all_verified) / max(len(all_verified), 1)
        ),
        "last_engine_run": lead_cache.get("last_run"),
    }


@app.get("/api/seasonal-tip")
async def get_seasonal_tip():
    """Get the current seasonal intelligence tip."""
    month = datetime.now().month
    tips = {
        (1, 2): {"icon": "🌧️", "title": "Post-Rain Cleanup Season", "body": "Winter rains are wrapping up. Gutters are clogged, walkways have debris. Push gutter cleaning and pressure washing.", "services": ["Gutter Cleaning", "Pressure Washing"]},
        (3, 4): {"icon": "☀️", "title": "Spring Push — Window & Solar Season", "body": "Pollen season just ended in San Diego. Homeowners are noticing dirty windows and dusty solar panels. Demand spikes 40% this month.", "services": ["Window Cleaning", "Solar Panel Cleaning"]},
        (5, 6): {"icon": "⚡", "title": "Peak Solar Season", "body": "San Diego sunshine is at its strongest. Dirty panels are losing 15-25% efficiency and homeowners see it on their bills.", "services": ["Solar Panel Cleaning", "Window Cleaning"]},
        (7, 8): {"icon": "🏖️", "title": "Summer Entertaining Season", "body": "BBQ season and outdoor entertaining. Homeowners want sharp patios and windows. HOAs are doing mid-year inspections.", "services": ["Window Cleaning", "Pressure Washing"]},
        (9, 10): {"icon": "🍂", "title": "Fall Prep Season", "body": "Leaves falling, rain coming. Smart homeowners prep gutters and exteriors before winter.", "services": ["Gutter Cleaning", "Pressure Washing"]},
        (11, 12): {"icon": "🎄", "title": "Holiday & Year-End Push", "body": "Holiday parties mean clean windows. Year-end HOA budgets need spending. Agents prepping January listings.", "services": ["Window Cleaning", "Gutter Cleaning"]},
    }
    for months, tip in tips.items():
        if month in range(months[0], months[1] + 1):
            return tip
    return tips[(3, 4)]  # default


@app.post("/api/engine/run")
async def trigger_engine_run():
    """Manually trigger a lead discovery run (for testing)."""
    try:
        result = await engine.run()
        
        # Update cache
        lead_cache["verified"] = result["verified_leads"]
        lead_cache["unverified"] = result["unverified_leads"]
        lead_cache["last_run"] = datetime.now().isoformat()
        
        # Add IDs to leads
        for i, lead in enumerate(lead_cache["verified"]):
            lead["id"] = f"v-{i+1}"
        for i, lead in enumerate(lead_cache["unverified"]):
            lead["id"] = f"u-{i+1}"

        return {
            "success": True,
            "verified_count": len(result["verified_leads"]),
            "unverified_count": len(result["unverified_leads"]),
            "duration_seconds": result["duration_seconds"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ── Run the server ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
