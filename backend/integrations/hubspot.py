import os
import json
import aiohttp
from datetime import datetime
from fastapi import Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from redis_client import add_key_value_redis, get_value_redis
from integrations.integration_item import IntegrationItem

# Environment variables
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/integrations/hubspot/oauth2callback")

# HubSpot API endpoints
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_API_BASE_URL = "https://api.hubapi.com"


async def authorize_hubspot(user_id, org_id):
    """Generate HubSpot OAuth2 authorization URL."""
    try:
        params = {
            "client_id": HUBSPOT_CLIENT_ID,
            "redirect_uri": HUBSPOT_REDIRECT_URI,
            "scope": "crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read",
            "response_type": "code",
            "state": f"{user_id}:{org_id}"
        }
        return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"
    except Exception as e:
        print(f"Error generating HubSpot auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def oauth2callback_hubspot(request: Request):
    """Handle OAuth2 callback from HubSpot."""
    try:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not found")

        state = request.query_params.get("state")
        if not state or ":" not in state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
            
        user_id, org_id = state.split(":")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                HUBSPOT_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": HUBSPOT_CLIENT_ID,
                    "client_secret": HUBSPOT_CLIENT_SECRET,
                    "redirect_uri": HUBSPOT_REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status != 200:
                    error_info = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=f"HubSpot API error: {error_info}")
                    
                data = await resp.json()
                if "access_token" not in data:
                    raise HTTPException(status_code=400, detail="Failed to retrieve access token")

                # Storeing tokens in Redis
                await add_key_value_redis(f"hubspot_credentials:{org_id}:{user_id}", json.dumps(data), expire=3600)

                #popup window
                close_window_script = """
                <html>
                    <script>
                        window.close();
                    </script>
                </html>
                """
                return HTMLResponse(content=close_window_script)

    except Exception as e:
        print(f"Error handling OAuth2 callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_hubspot_credentials(user_id, org_id):
    """Retrieve HubSpot credentials from Redis."""
    credentials = await get_value_redis(f"hubspot_credentials:{org_id}:{user_id}")
    if not credentials:
        raise HTTPException(status_code=400, detail="No HubSpot credentials found")
        
    return credentials


async def process_hubspot_items(response_json, item_type, is_directory):
    """Process HubSpot API response into IntegrationItem objects."""
    items = []
    
    for item in response_json.get("results", []):
        properties = item.get("properties", {})
        
        # Convert timestamp strings to datetime
        creation_time = None
        last_modified_time = None
        
        if properties.get("createdate"):
            try:
                creation_time = datetime.fromisoformat(properties.get("createdate").replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
                
        if properties.get("lastmodifieddate"):
            try:
                last_modified_time = datetime.fromisoformat(properties.get("lastmodifieddate").replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        
        # Generate name based on item type
        name = "Unknown"
        if item_type == "Contact":
            name = f"{properties.get('firstname', '')} {properties.get('lastname', '')}".strip() 
            if not name:
                name = properties.get('email', 'Unknown Contact')
        elif item_type == "Company":
            name = properties.get("name", "Unknown Company")
        elif item_type == "Deal":
            name = properties.get("dealname", "Unknown Deal")
        
        # Create URL to view the item in HubSpot
        url = None
        if item_type == "Contact":
            url = f"https://app.hubspot.com/contacts/contacts/{item['id']}"
        elif item_type == "Company":
            url = f"https://app.hubspot.com/contacts/companies/{item['id']}"
        elif item_type == "Deal":
            url = f"https://app.hubspot.com/contacts/deals/{item['id']}"
            
        # Create IntegrationItem object
        integration_item = IntegrationItem(
            id=item["id"],
            type=item_type,
            directory=is_directory,
            name=name,
            creation_time=creation_time,
            last_modified_time=last_modified_time,
            url=url,
        )
        
        items.append(integration_item)
        
    return items


async def get_items_hubspot(credentials):
    """Fetch items from HubSpot and return them as IntegrationItem objects."""
    try:
        credentials_dict = json.loads(credentials)
        access_token = credentials_dict.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Invalid credentials: missing access token")

        headers = {"Authorization": f"Bearer {access_token}"}
        integration_items = []

        # Define endpoints to fetch with appropriate mapping to IntegrationItem fields
        endpoints = [
            {
                "url": f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/contacts", 
                "type": "Contact",
                "directory": False
            },
            {
                "url": f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/companies", 
                "type": "Company",
                "directory": False
            },
            {
                "url": f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/deals", 
                "type": "Deal",
                "directory": False
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    async with session.get(endpoint["url"], headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            items = await process_hubspot_items(data, endpoint["type"], endpoint["directory"])
                            integration_items.extend(items)
                        else:
                            print(f"Failed to fetch {endpoint['type']} data: {resp.status}")
                except Exception as e:
                    print(f"Error fetching {endpoint['type']} data: {e}")

            
            # Print items for testing as suggested in the problem statement
            print(f"Retrieved {len(integration_items)} HubSpot integration items")
            for item in integration_items[:5]:  # Printing first 5 items as a sample
                print(f"Item: {item.__dict__}")
                
            return integration_items

    except Exception as e:
        print(f"Error fetching data from HubSpot: {e}")
        raise HTTPException(status_code=500, detail=str(e))