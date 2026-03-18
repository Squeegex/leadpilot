"""
LeadPilot — Property Data Engine
Fetches property data from RentCast API for target zip codes.
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from config import Config


class PropertyFetcher:
    """Finds properties in target zip codes that are good candidates for exterior services."""

    def __init__(self):
        self.api_key = Config.RENTCAST_API_KEY
        self.base_url = Config.RENTCAST_BASE_URL
        self.headers = {"X-Api-Key": self.api_key, "Accept": "application/json"}

    async def search_properties(self, zip_code: str, limit: int = 20) -> list:
        """Search for residential properties in a zip code."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/properties",
                    headers=self.headers,
                    params={
                        "zipCode": zip_code,
                        "limit": limit,
                        "propertyType": "Single Family,Condo,Townhouse",
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"RentCast error for {zip_code}: {response.status_code}")
                    return []
            except Exception as e:
                print(f"Error fetching properties for {zip_code}: {e}")
                return []

    async def search_recent_sales(self, zip_code: str, days_back: int = 30) -> list:
        """Find recently sold properties — new owners likely need services."""
        async with httpx.AsyncClient() as client:
            try:
                date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                response = await client.get(
                    f"{self.base_url}/sale-listings",
                    headers=self.headers,
                    params={
                        "zipCode": zip_code,
                        "status": "Sold",
                        "dateSoldAfter": date_from,
                        "limit": 10,
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    return response.json()
                return []
            except Exception as e:
                print(f"Error fetching sales for {zip_code}: {e}")
                return []

    async def search_active_listings(self, zip_code: str) -> list:
        """Find homes currently for sale — real estate agents need curb appeal."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/sale-listings",
                    headers=self.headers,
                    params={
                        "zipCode": zip_code,
                        "status": "Active",
                        "limit": 10,
                    },
                    timeout=30,
                )
                if response.status_code == 200:
                    return response.json()
                return []
            except Exception as e:
                print(f"Error fetching listings for {zip_code}: {e}")
                return []

    def score_property(self, prop: dict) -> dict:
        """Score a property on how likely they need exterior services."""
        score = 50  # base score
        services_needed = []
        reasons = []

        # Property age — older homes need more maintenance
        year_built = prop.get("yearBuilt", 0)
        if year_built and year_built < 2000:
            score += 10
            services_needed.extend(["pressure_washing", "gutter_cleaning"])
            reasons.append(f"Built in {year_built} — likely needs exterior maintenance")
        elif year_built and year_built < 2010:
            score += 5
            services_needed.append("window_cleaning")

        # Lot size — larger lots = more exterior surface
        sqft = prop.get("lotSize", 0) or prop.get("squareFootage", 0)
        if sqft and sqft > 2000:
            score += 8
            services_needed.append("window_cleaning")
            reasons.append(f"{sqft:,} sqft — larger property with more exterior surface")

        # Property value — higher value = more likely to pay for services
        value = prop.get("price", 0) or prop.get("estimatedValue", 0)
        if value and value > 1000000:
            score += 15
            reasons.append(f"High-value property (${value:,.0f}) — owner likely invests in maintenance")
        elif value and value > 500000:
            score += 10

        # Multi-unit = higher contract value
        units = prop.get("units", 1)
        if units and units > 1:
            score += 12
            reasons.append(f"Multi-unit property ({units} units) — recurring contract potential")

        # San Diego solar assumption — high solar adoption
        # Properties in 92014, 92037 (coastal affluent) very likely to have solar
        zip_code = prop.get("zipCode", "")
        if zip_code in ["92014", "92037", "92106"]:
            score += 8
            services_needed.append("solar_panel_cleaning")
            reasons.append("Located in high solar adoption neighborhood")

        # Default services if none detected
        if not services_needed:
            services_needed = ["window_cleaning", "pressure_washing"]

        # Remove duplicates
        services_needed = list(set(services_needed))

        # Estimate job value
        est_value = self._estimate_value(services_needed, units or 1)

        return {
            "score": min(score, 100),
            "services_needed": services_needed,
            "reasons": reasons,
            "est_value": est_value,
        }

    def _estimate_value(self, services: list, units: int = 1) -> str:
        """Estimate the dollar value of a job."""
        base_prices = {
            "window_cleaning": 150,
            "solar_panel_cleaning": 180,
            "pressure_washing": 200,
            "gutter_cleaning": 120,
        }
        total = sum(base_prices.get(s, 100) for s in services) * max(units, 1)
        if total > 500:
            return f"${total:,}+"
        return f"${total:,}"

    def extract_lead(self, prop: dict, source: str = "property") -> dict:
        """Convert a raw property record into a LeadPilot lead."""
        scoring = self.score_property(prop)

        # Extract address
        address_parts = [
            prop.get("addressLine1", ""),
            prop.get("city", "San Diego"),
            prop.get("state", "CA"),
            prop.get("zipCode", ""),
        ]
        address = ", ".join(p for p in address_parts if p)

        # Determine lead type
        units = prop.get("units", 1)
        if units and units > 4:
            lead_type = "commercial"
        elif units and units > 1:
            lead_type = "property_manager"
        else:
            lead_type = "homeowner"

        return {
            "name": prop.get("addressLine1", "Unknown Property"),
            "contact_name": prop.get("ownerName", "Homeowner"),
            "lead_type": lead_type,
            "address": address,
            "city": prop.get("city", "San Diego"),
            "state": prop.get("state", "CA"),
            "zip_code": prop.get("zipCode", ""),
            "latitude": prop.get("latitude"),
            "longitude": prop.get("longitude"),
            "phone": prop.get("ownerPhone", ""),
            "email": prop.get("ownerEmail", ""),
            "services_needed": scoring["services_needed"],
            "source": source,
            "reason": " | ".join(scoring["reasons"]) if scoring["reasons"] else "Property in target service area",
            "score": scoring["score"],
            "est_value": scoring["est_value"],
            "property_type": prop.get("propertyType", "single_family"),
            "property_year_built": prop.get("yearBuilt"),
            "lot_size": str(prop.get("lotSize", "")),
            "has_solar": False,  # Will be updated by solar detection
        }

    async def fetch_all_leads(self, zip_codes: list = None) -> list:
        """Main function — fetch leads from all zip codes."""
        if zip_codes is None:
            zip_codes = Config.TARGET_ZIPS

        all_leads = []

        for zip_code in zip_codes:
            print(f"🔍 Searching {zip_code}...")

            # Get properties
            properties = await self.search_properties(zip_code, limit=10)
            for prop in properties:
                lead = self.extract_lead(prop, source="property")
                all_leads.append(lead)

            # Get active listings (for real estate agent leads)
            listings = await self.search_active_listings(zip_code)
            for listing in listings:
                lead = self.extract_lead(listing, source="property")
                lead["lead_type"] = "real_estate_agent"
                lead["reason"] = f"Active listing — curb appeal services needed before showings | {lead['reason']}"
                lead["score"] = min(lead["score"] + 10, 100)
                all_leads.append(lead)

            # Small delay to respect rate limits
            await asyncio.sleep(0.5)

        # Sort by score (best leads first) and limit
        all_leads.sort(key=lambda x: x["score"], reverse=True)

        print(f"✅ Found {len(all_leads)} total leads across {len(zip_codes)} zip codes")
        return all_leads[:Config.MAX_LEADS_PER_DAY * 3]  # Fetch extra, we'll filter after verification
