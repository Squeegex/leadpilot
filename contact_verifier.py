"""
LeadPilot — Contact Verification Engine
Verifies phone numbers and email addresses before leads reach the dashboard.
"""

import httpx
from config import Config


class ContactVerifier:
    """Verifies phone numbers and emails using NumVerify and Emailable APIs."""

    def __init__(self):
        self.numverify_key = Config.NUMVERIFY_API_KEY
        self.emailable_key = Config.EMAILABLE_API_KEY

    async def verify_phone(self, phone: str) -> dict:
        """
        Check if a phone number is real, active, and what type it is.
        Returns: { status: 'verified'|'likely'|'unverified', line_type: 'mobile'|'landline', ... }
        """
        if not phone or phone == "—" or len(phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")) < 7:
            return {"status": "unverified", "line_type": None, "raw_phone": phone}

        # Clean the phone number — remove formatting
        clean_phone = phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "").replace("+", "")
        if len(clean_phone) == 10:
            clean_phone = "1" + clean_phone  # Add US country code

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{Config.NUMVERIFY_BASE_URL}/validate",
                    params={
                        "access_key": self.numverify_key,
                        "number": clean_phone,
                        "country_code": "US",
                        "format": 1,
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("valid", False):
                        line_type = data.get("line_type", "unknown")
                        return {
                            "status": "verified",
                            "line_type": line_type,  # 'mobile', 'landline', 'voip', etc.
                            "carrier": data.get("carrier", ""),
                            "location": data.get("location", ""),
                            "formatted": data.get("international_format", phone),
                            "is_textable": line_type in ["mobile", "voip"],
                            "raw_phone": phone,
                        }
                    else:
                        return {"status": "unverified", "line_type": None, "raw_phone": phone}
                else:
                    # API error — mark as likely (don't penalize the lead for API issues)
                    return {"status": "likely", "line_type": None, "raw_phone": phone}

            except Exception as e:
                print(f"Phone verification error: {e}")
                return {"status": "likely", "line_type": None, "raw_phone": phone}

    async def verify_email(self, email: str) -> dict:
        """
        Check if an email address exists and can receive messages.
        Returns: { status: 'verified'|'likely'|'unverified', ... }
        """
        if not email or email == "—" or "@" not in email:
            return {"status": "unverified", "raw_email": email}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{Config.EMAILABLE_BASE_URL}/verify",
                    params={
                        "email": email,
                        "api_key": self.emailable_key,
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    data = response.json()
                    state = data.get("state", "unknown")
                    score = data.get("score", 0)

                    # Emailable states: deliverable, undeliverable, risky, unknown
                    if state == "deliverable":
                        return {
                            "status": "verified",
                            "state": state,
                            "score": score,
                            "is_free_provider": data.get("free", False),
                            "is_disposable": data.get("disposable", False),
                            "raw_email": email,
                        }
                    elif state == "risky":
                        return {
                            "status": "likely",
                            "state": state,
                            "score": score,
                            "raw_email": email,
                        }
                    else:
                        return {"status": "unverified", "state": state, "raw_email": email}
                else:
                    return {"status": "likely", "raw_email": email}

            except Exception as e:
                print(f"Email verification error: {e}")
                return {"status": "likely", "raw_email": email}

    async def verify_lead(self, lead: dict) -> dict:
        """
        Verify all contact info for a single lead.
        Returns the lead with verification statuses updated.
        """
        # Verify phone
        phone_result = await self.verify_phone(lead.get("phone", ""))
        lead["phone_verified"] = phone_result["status"]
        if phone_result.get("formatted"):
            lead["phone"] = phone_result["formatted"]

        # Verify email
        email_result = await self.verify_email(lead.get("email", ""))
        lead["email_verified"] = email_result["status"]

        # Address is always considered verified (comes from property records)
        lead["address_verified"] = "verified"

        # Determine if lead qualifies for the verified tab
        # At least phone OR email must be verified
        has_verified_contact = (
            lead["phone_verified"] == "verified"
            or lead["email_verified"] == "verified"
        )
        lead["is_fully_verified"] = has_verified_contact

        return lead

    async def verify_batch(self, leads: list) -> tuple:
        """
        Verify a batch of leads. Returns (verified_leads, unverified_leads).
        """
        verified = []
        unverified = []

        for lead in leads:
            verified_lead = await self.verify_lead(lead)

            if verified_lead["is_fully_verified"]:
                verified.append(verified_lead)
            else:
                unverified.append(verified_lead)

        print(f"✅ Verification complete: {len(verified)} verified, {len(unverified)} unverified")
        return verified, unverified
