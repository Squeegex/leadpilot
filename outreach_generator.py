"""
LeadPilot — AI Outreach Message Generator
Uses Claude to write personalized outreach messages for each lead.
"""

import httpx
from config import Config


class OutreachGenerator:
    """Generates personalized text/call scripts for each lead using AI."""

    def __init__(self):
        self.api_key = Config.ANTHROPIC_API_KEY
        self.model = "claude-sonnet-4-20250514"

    async def generate_message(self, lead: dict, business_name: str = "Squeegex") -> str:
        """Generate a personalized outreach message for a lead."""

        service_names = [Config.SERVICE_NAMES.get(s, s) for s in lead.get("services_needed", [])]
        services_str = ", ".join(service_names)

        prompt = f"""You are writing a short, friendly text message for {business_name}, 
an exterior services company in San Diego, to send to a potential customer.

Lead details:
- Name: {lead.get('contact_name', 'Homeowner')}
- Type: {lead.get('lead_type', 'homeowner')}
- Property: {lead.get('address', 'San Diego')}
- Why they're a good lead: {lead.get('reason', 'Property in target service area')}
- Services they likely need: {services_str}
- Estimated job value: {lead.get('est_value', '$200+')}

Write a casual, friendly text message (under 160 words) that:
1. Mentions something specific about their property or situation
2. Explains the benefit of the service (not just the service itself)
3. Offers a free estimate
4. Includes a soft call to action
5. Sounds like a real local business owner texting, not a marketing email

Do NOT use exclamation marks excessively. Do NOT sound salesy or corporate.
Just write the message text, nothing else. No quotes around it."""

        if not self.api_key:
            # Fallback template if no Claude API key is set
            return self._fallback_message(lead, business_name, services_str)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 300,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["content"][0]["text"].strip()
                else:
                    print(f"Claude API error: {response.status_code}")
                    return self._fallback_message(lead, business_name, services_str)

            except Exception as e:
                print(f"Outreach generation error: {e}")
                return self._fallback_message(lead, business_name, services_str)

    def _fallback_message(self, lead: dict, business_name: str, services_str: str) -> str:
        """Generate a template-based message when Claude API isn't available."""
        contact = lead.get("contact_name", "there")
        first_name = contact.split()[0] if contact and contact != "Homeowner" else "there"
        address_short = lead.get("address", "your area").split(",")[0]
        lead_type = lead.get("lead_type", "homeowner")

        if lead_type == "real_estate_agent":
            return (
                f"Hi {first_name} — I saw your listing at {address_short}. "
                f"I help agents boost curb appeal with {services_str.lower()} before showings. "
                f"Clean exteriors can make a great first impression on buyers. "
                f"Want a quick free estimate? I can usually get it done within 48 hours."
            )
        elif lead_type in ["property_manager", "hoa"]:
            return (
                f"Hi {first_name} — I work with property managers in San Diego "
                f"to keep their buildings looking sharp. I offer {services_str.lower()} "
                f"with multi-property discounts. Would you be open to a quick conversation "
                f"about a maintenance package?"
            )
        elif lead_type == "commercial":
            return (
                f"Hi — I handle {services_str.lower()} for commercial properties in your area. "
                f"I noticed {address_short} could benefit from an exterior refresh. "
                f"I offer monthly maintenance packages so you never have to think about it. "
                f"Can I send over a quote?"
            )
        else:
            return (
                f"Hi {first_name} — I'm a local {services_str.lower()} specialist "
                f"in your neighborhood. I noticed your property at {address_short} "
                f"might benefit from some exterior TLC. Would you be interested in a "
                f"free estimate? No pressure at all."
            )

    async def generate_batch(self, leads: list, business_name: str = "Squeegex") -> list:
        """Generate outreach messages for a batch of leads."""
        for lead in leads:
            lead["outreach_message"] = await self.generate_message(lead, business_name)
        
        print(f"✅ Generated {len(leads)} outreach messages")
        return leads
