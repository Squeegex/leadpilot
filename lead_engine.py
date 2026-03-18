"""
LeadPilot — Overnight Lead Discovery Engine
This is the main orchestrator that runs every night at ~4:00 AM PT.
It finds properties, verifies contacts, generates outreach, and stores leads.
"""

import asyncio
from datetime import datetime
from property_fetcher import PropertyFetcher
from contact_verifier import ContactVerifier
from outreach_generator import OutreachGenerator
from config import Config


class LeadEngine:
    """Main engine that orchestrates the entire lead discovery pipeline."""

    def __init__(self):
        self.property_fetcher = PropertyFetcher()
        self.verifier = ContactVerifier()
        self.outreach = OutreachGenerator()

    async def run(self, user_config: dict = None) -> dict:
        """
        Run the full lead discovery pipeline.
        
        Steps:
        1. Fetch properties from target zip codes
        2. Score and filter leads
        3. Verify phone numbers and emails
        4. Generate personalized outreach messages
        5. Store in database
        
        Returns a summary of what was found.
        """
        start_time = datetime.now()
        zip_codes = (user_config or {}).get("target_zips", Config.TARGET_ZIPS)
        max_leads = (user_config or {}).get("leads_per_day", Config.MAX_LEADS_PER_DAY)
        business_name = (user_config or {}).get("business_name", "Squeegex")

        print("=" * 60)
        print(f"🚀 LeadPilot Engine Starting — {start_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"📍 Searching: {', '.join(zip_codes)}")
        print(f"🎯 Target: {max_leads} verified leads")
        print("=" * 60)

        # ── Step 1: Fetch raw property data ──
        print("\n📡 Step 1: Fetching property data...")
        raw_leads = await self.property_fetcher.fetch_all_leads(zip_codes)
        print(f"   Found {len(raw_leads)} raw leads")

        # ── Step 2: Filter by minimum score ──
        print("\n🏆 Step 2: Scoring and filtering...")
        scored_leads = [l for l in raw_leads if l["score"] >= Config.MIN_LEAD_SCORE]
        scored_leads.sort(key=lambda x: x["score"], reverse=True)
        print(f"   {len(scored_leads)} leads meet minimum score threshold ({Config.MIN_LEAD_SCORE}+)")

        # ── Step 3: Verify contact info ──
        print("\n🔍 Step 3: Verifying contact info...")
        # Only verify up to 3x our daily target (to save API calls)
        to_verify = scored_leads[:max_leads * 3]
        verified_leads, unverified_leads = await self.verifier.verify_batch(to_verify)

        # Take only what we need for the day
        verified_leads = verified_leads[:max_leads]
        unverified_leads = unverified_leads[:max_leads]

        # ── Step 4: Generate outreach messages ──
        print("\n✍️ Step 4: Generating outreach messages...")
        verified_leads = await self.outreach.generate_batch(verified_leads, business_name)
        unverified_leads = await self.outreach.generate_batch(unverified_leads, business_name)

        # ── Step 5: Add seasonal intelligence ──
        print("\n🌤️ Step 5: Applying seasonal intelligence...")
        current_month = datetime.now().month
        seasonal_services = self._get_seasonal_services(current_month)
        for lead in verified_leads + unverified_leads:
            # Boost score for leads that match seasonal demand
            matching_services = set(lead.get("services_needed", [])) & set(seasonal_services)
            if matching_services:
                lead["score"] = min(lead["score"] + 5, 100)

        # ── Summary ──
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "status": "completed",
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_seconds": round(duration, 1),
            "zip_codes_searched": zip_codes,
            "raw_leads_found": len(raw_leads),
            "leads_scored": len(scored_leads),
            "leads_verified": len(verified_leads),
            "leads_unverified": len(unverified_leads),
            "verified_leads": verified_leads,
            "unverified_leads": unverified_leads,
        }

        print("\n" + "=" * 60)
        print(f"✅ LeadPilot Engine Complete — {duration:.1f} seconds")
        print(f"   📊 Raw leads found: {len(raw_leads)}")
        print(f"   ✓ Verified leads: {len(verified_leads)}")
        print(f"   ? Unverified leads: {len(unverified_leads)}")
        print("=" * 60)

        return summary

    def _get_seasonal_services(self, month: int) -> list:
        """Get which services to prioritize based on current month."""
        seasonal_map = {
            1: ["gutter_cleaning", "pressure_washing"],
            2: ["gutter_cleaning", "pressure_washing"],
            3: ["window_cleaning", "solar_panel_cleaning"],
            4: ["window_cleaning", "solar_panel_cleaning"],
            5: ["solar_panel_cleaning", "window_cleaning"],
            6: ["solar_panel_cleaning", "window_cleaning"],
            7: ["window_cleaning", "pressure_washing"],
            8: ["window_cleaning", "pressure_washing"],
            9: ["gutter_cleaning", "pressure_washing"],
            10: ["gutter_cleaning", "pressure_washing"],
            11: ["window_cleaning", "gutter_cleaning"],
            12: ["window_cleaning", "gutter_cleaning"],
        }
        return seasonal_map.get(month, ["window_cleaning", "pressure_washing"])


# ── Run directly for testing ──
if __name__ == "__main__":
    engine = LeadEngine()
    result = asyncio.run(engine.run())
    
    print(f"\n🎯 Top verified leads:")
    for i, lead in enumerate(result["verified_leads"][:5], 1):
        print(f"  {i}. {lead['name']} — Score: {lead['score']} — {lead['est_value']}")
        print(f"     Phone: {lead['phone']} ({lead['phone_verified']})")
        print(f"     Email: {lead['email']} ({lead['email_verified']})")
        print(f"     Services: {', '.join(lead['services_needed'])}")
        print()
