import time
print(f"UNIX timestamp before import: {time.time()}")

# Run the clerk_backend_api patch first
import os
import subprocess
import sys

# Try to run our patch script
try:
    patch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patch_clerk.py")
    if os.path.exists(patch_script):
        print("Running clerk_backend_api patch script...")
        # Option 1: Run as subprocess (for deployment environments where we have permissions)
        try:
            result = subprocess.run([sys.executable, patch_script], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(f"Patch script error: {result.stderr}")
        except Exception as e:
            print(f"Error running patch script: {e}")
        
        # Option 2: Import and run directly (in case subprocess isn't allowed)
        try:
            import patch_clerk
            patch_result = patch_clerk.main()
            print(f"Direct patch result: {patch_result}")
        except Exception as e:
            print(f"Error importing patch_clerk: {e}")
    else:
        print(f"Patch script not found at {patch_script}")
except Exception as e:
    print(f"General error in patching step: {e}")

# Import other modules
import json
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends, Response
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
import os
import requests
from clerk_backend_api import Clerk
from datetime import datetime, timedelta
import re
from pymongo import MongoClient
import socket
import hashlib
import aiohttp
import jwt

load_dotenv()

print(f"UNIX timestamp after import: {time.time()}")

# MongoDB Connection
MONGO_CONNECTION_STRING = os.getenv('MONGO_CONNECTION_STRING_P1') + os.getenv('MONGODB_USER_PWD') + os.getenv('MONGO_CONNECTION_STRING_P2')
mongo_client = MongoClient(MONGO_CONNECTION_STRING)
db = mongo_client['easywire']
alerts_collection = db['alerts']

# Initialize Clerk
clerk = Clerk(bearer_auth=os.getenv('CLERK_SECRET_KEY'))

app = FastAPI()

print("UNIX timestamp after Clerk and FastAPI initialization:", time.time())

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=512)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Cache configuration
CACHE_DURATION = 300  # 5 minutes in seconds

print("UNIX timestamp after middleware:", time.time())

# Clerk authentication middleware
async def get_auth_user(request: Request):
    # Check for Clerk session token in cookies
    # First try __session, then __client
    session_token = request.cookies.get('__session') or request.cookies.get('__client')
    print("Cookies:", request.cookies)
    if not session_token:
        # Also check Authorization header
        auth_header = request.headers.get('Authorization')
        print("Authorization header:", auth_header)
        if auth_header and auth_header.startswith('Bearer '):
            session_token = auth_header.split(' ')[1]
        else:
            print("No session token found in cookies or Authorization header")
            return None
    
    print("Session token found:", session_token[:10] + "..." if session_token else None)
            
    try:
        print("Verifying session token...")
        # Decode the JWT to get the user ID
        decoded = jwt.decode(session_token, options={"verify_signature": False})
        user_id = decoded.get('sub')  # 'sub' claim contains the user ID
        print("User ID from token:", user_id)
        
        if not user_id:
            print("No user ID found in token")
            return None
            
        # Get user directly using the ID from the token
        user = clerk.users.get(user_id=user_id)
        print("User retrieved from Clerk")
        return user
    except Exception as e:
        print(f"Auth error: {str(e)}")
        return None

# Protected route dependency
async def require_auth(user = Depends(get_auth_user)):
    if not user:
        return {"authenticated": False, "message": "Please Sign In"}
    return {"authenticated": True, "user": user}

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
data_dir = os.path.join(os.path.dirname(__file__), "data")

# Configure static files with caching and CDN headers
class CachedStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # Cache for 1 year on CDN and browser
            response.headers["Cache-Control"] = "public, max-age=31536000, s-maxage=31536000, immutable"
            response.headers["Vary"] = "Accept-Encoding"
            # Add CDN-specific headers
            response.headers["Vercel-CDN-Cache-Control"] = "max-age=31536000"
            response.headers["CDN-Cache-Control"] = "max-age=31536000"
        return response

app.mount(
    "/templates",
    CachedStaticFiles(
        directory=templates_dir,
    ),
    name="templates",
)

app.mount(
    "/data",
    CachedStaticFiles(
        directory=data_dir,
    ),
    name="data",
)

app.mount(
    "/homepage_files",
    CachedStaticFiles(
        directory=templates_dir+"/homepage_files",
    ),
    name="homepage_files",
)

templates = Jinja2Templates(directory=templates_dir)

# Valid currency codes (common ones)
VALID_CURRENCIES = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'INR', 'NZD'}

@app.get("/")
async def root(request: Request, response: Response, user = Depends(get_auth_user)):
    """
    ### Root Endpoint
    A function that serves the root endpoint of the API. It returns a static HTML for non-authenticated users
    and a dynamic template for authenticated users.
    """
    print("UNIX timestamp at the start of root:", time.time())
    # Generate ETag based on template file modification time
    template_path = os.path.join(templates_dir, "home.html")
    template_mtime = str(os.path.getmtime(template_path))
    etag = hashlib.md5(template_mtime.encode()).hexdigest()
    
    # Check if client has valid cached version
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    
    # Set common caching headers
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = f"public, max-age={CACHE_DURATION}, s-maxage={CACHE_DURATION}, stale-while-revalidate"
    response.headers["Vercel-CDN-Cache-Control"] = f"max-age={CACHE_DURATION}"
    response.headers["CDN-Cache-Control"] = f"max-age={CACHE_DURATION}"

    # For non-authenticated users, serve static HTML from cache if available
    static_html_path = os.path.join(templates_dir, "static_home.html")

    if not user:
        print("UNIX timestamp at the start of FileResponse:", time.time())
        # Serve static file with proper headers
        return FileResponse(
            static_html_path,
            headers=response.headers,
            media_type="text/html"
        )

    # For authenticated users, show loading state while template renders
    if user:
        print("UNIX timestamp at the start of TemplateResponse:", time.time())
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "show_loading": True,
                "user": user
            }
        )
    
    # If static HTML doesn't exist or is older than template, regenerate it
    should_regenerate = (
        not os.path.exists(static_html_path) or 
        os.path.getmtime(static_html_path) < os.path.getmtime(template_path)
    )
    
    if should_regenerate:
        print("UNIX timestamp at the start of TemplateResponse:", time.time())
        # Generate static version by rendering template without user
        static_content = templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "static_render": True  # Flag to indicate static rendering
            }
        ).body.decode()
        
        # Save to static file
        with open(static_html_path, "w") as f:
            f.write(static_content)
    
    print("UNIX timestamp at the start of FileResponse:", time.time())
    # Serve static file with proper headers
    return FileResponse(
        static_html_path,
        headers=response.headers,
        media_type="text/html"
    )

@app.post("/data")
async def data(
    request: Request,
    amount: Annotated[str, Form()],
    from_currency: Annotated[str, Form()],
    to_currency: Annotated[str, Form()],
    date: Annotated[str, Form()],
    email: Annotated[str, Form()],
    user = Depends(get_auth_user)
):
    errors = []
    
    # Amount validation
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            errors.append("Amount must be greater than 0")
    except ValueError:
        errors.append("Please enter a valid amount")

    # Currency validation
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency not in VALID_CURRENCIES:
        errors.append(f"Invalid 'from' currency. Supported currencies: {', '.join(sorted(VALID_CURRENCIES))}")
    if to_currency not in VALID_CURRENCIES:
        errors.append(f"Invalid 'to' currency. Supported currencies: {', '.join(sorted(VALID_CURRENCIES))}")
    if from_currency == to_currency:
        errors.append("'From' and 'To' currencies must be different")

    # Date validation
    try:
        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        if parsed_date < datetime.now():
            errors.append("Date must be in the future")
    except ValueError:
        errors.append("Please enter a valid date")

    # Email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        errors.append("Please enter a valid email address")

    # If there are any errors, return them to the user
    if errors:
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "errors": errors,
                "form_data": {  # Return form data to repopulate fields
                    "amount": amount,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "date": date,
                    "email": email
                }
            },
            status_code=400
        )
    
    # All validations passed, proceed with the request
    print(f"Processing transaction: {amount} {from_currency} to {to_currency}")
    
    # Only use caching if user is signed in
    if user:
        # Create a secure hash of the email using SHA-256
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        cache_key = f"{from_currency}_{to_currency}_{email_hash}_{amount}"
        cached_data = db.forex_cache.find_one({"cache_key": cache_key})
        
        if cached_data:
            forex_data = cached_data["forex_data"]
            print(f"Using cached forex data for {cache_key}")
        else:
            forex_data = await fetch_forex_data(from_currency, to_currency)
            # Cache the forex data only for signed in users
            db.forex_cache.insert_one({
                "cache_key": cache_key,
                "forex_data": forex_data,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=24)  # Cache for 24 hours
            })
            print(f"Cached new forex data for {cache_key}")
    else:
        # For non-signed in users, directly fetch without caching
        forex_data = await fetch_forex_data(from_currency, to_currency)
    
    # Store the alert in MongoDB with the forex data
    alert_data = {
        "amount": float(amount),
        "from_currency": from_currency,
        "to_currency": to_currency,
        "target_date": datetime.strptime(date, '%Y-%m-%d'),
        "email": email,
        "created_at": datetime.utcnow(),
        "forex_data": forex_data  # Store the forex data with the alert
    }
    alerts_collection.insert_one(alert_data)
    
    # Redirect to success page with the selected currencies
    return RedirectResponse(url=f"/success?from_curr={from_currency}&to_curr={to_currency}", status_code=303)

async def fetch_forex_data(from_currency: str, to_currency: str):
    """Helper function to fetch forex data from backend API and historical data from Alpha Vantage"""
    try:
        # Fetch main forex data from backend (cached)
        backend_url = "https://ewb.aryankeluskar.com"
        url = f"{backend_url}/forex_data?from_currency={from_currency}&to_currency={to_currency}"
        
        async with aiohttp.ClientSession() as session:
            # Fetch main forex data
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Error fetching forex data from backend")
                forex_data = await response.json()
                
                return forex_data
                
    except Exception as e:
        print(f"Error fetching forex data: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to fetch forex data. Please try again later.")

# @app.get("/graph/usd_inr_all")
# async def graph_usd_inr_all():
#     return FileResponse("data/usd_inr_all.png")

@app.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join(templates_dir, "favicon.ico"))

@app.get("/success")
async def success(request: Request, from_curr: str, to_curr: str, user = Depends(get_auth_user)):
    """
    Endpoint that fetches forex data and displays it using a template
    """
    try:
        # Validate currency codes again as a security measure
        from_curr = from_curr.upper()
        to_curr = to_curr.upper()
        if from_curr not in VALID_CURRENCIES or to_curr not in VALID_CURRENCIES:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Invalid currency codes provided"
                },
                status_code=400
            )

        # Try to get the most recent alert with these currencies
        latest_alert = alerts_collection.find_one(
            {
                "from_currency": from_curr,
                "to_currency": to_curr
            },
            sort=[("created_at", -1)]
        )

        if latest_alert and "forex_data" in latest_alert:
            print(f"Using forex data from latest alert for {from_curr} to {to_curr}")
            forex_data = latest_alert["forex_data"]
        else:
            # Only use cache for signed in users
            if user:
                # Create a secure hash for default user
                default_hash = hashlib.sha256('default'.encode()).hexdigest()
                cache_key = f"{from_curr}_{to_curr}_{default_hash}_{1}"  # Use 1 as default amount for cache
                cached_data = db.forex_cache.find_one({
                    "cache_key": cache_key,
                    "expires_at": {"$gt": datetime.utcnow()}  # Check if cache hasn't expired
                })
                
                if cached_data:
                    print(f"Using cached forex data for {from_curr} to {to_curr}")
                    forex_data = cached_data["forex_data"]
                else:
                    forex_data = await fetch_forex_data(from_curr, to_curr)
                    # Cache the new forex data
                    db.forex_cache.insert_one({
                        "cache_key": cache_key,
                        "forex_data": forex_data,
                        "created_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(hours=24)
                    })
                    print(f"Cached new forex data for {cache_key}")
            else:
                # For non-signed in users, directly fetch without caching
                forex_data = await fetch_forex_data(from_curr, to_curr)

        if not forex_data:
            raise ValueError("Empty response from forex service")
        
        # load historical data file names from data/historical_data where file name is from_curr_to_curr_timestamp.json
        historical_data = []
        for file in os.listdir(data_dir+"/historical_data"):
            if f"{from_curr}_{to_curr}_" in file:
                historical_data.append(file)

        # only keep the latest (ie: the one with the highest timestamp, ie: the one with the highest number in its name. it does not have the timestamp in the json)
        latest_timestamp = 0
        latest_file = None
        for file in historical_data:
            curr_timestamp = int(file.split("_")[-1].split(".")[0])
            if curr_timestamp > latest_timestamp:
                latest_timestamp = curr_timestamp
                latest_file = file

        print(f"Latest historical data file: {latest_file}")

        is_data_available = 0

        if latest_file:
            is_data_available = 1
            historical_data = json.load(open(f"{data_dir}/historical_data/{latest_file}", "r"))

            # if historical data is empty, set it to None
            if not historical_data:
                historical_data = None

            forex_data["historical_data"] = historical_data

            # Load forecast data
            forecast_file = os.path.join(data_dir, "forecast_data", f"{from_curr}_{to_curr}_forecast.json")
            if os.path.exists(forecast_file):
                with open(forecast_file, 'r') as f:
                    forex_data["forecast_data"] = json.load(f)
            else:
                forex_data["forecast_data"] = {}

        else:
            print("No historical data available")
            forex_data["historical_data"] = {}
            forex_data["historical_data"]["historical_data"] = {}
            forex_data["forecast_data"] = {}
            forex_data["forecast_data"]["forecast_data"] = {}
            is_data_available = 0

        print(f"Is data available: {is_data_available}")
        print(f"Forecast data: {forex_data}")
            
        # Add success message to the template
        return templates.TemplateResponse(
            "success.html",
            { 
                "from_curr": from_curr,
                "to_curr": to_curr,
                "request": request,
                "forex_data": forex_data,
                "success_message": "Successfully fetched forex data!",
                "is_data_available": is_data_available
            }
        )

    except requests.Timeout:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "The backend is taking too long to respond. Please try again or check your internet connection."
            },
            status_code=504
        )
    except requests.ConnectionError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Unable to connect to our backend. Please check your internet connection and try again."
            },
            status_code=503
        )
    except requests.RequestException as e:
        import sys
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"API Error at line {exc_tb.tb_lineno}: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Unable to fetch forex data (line {exc_tb.tb_lineno}). Please try again later."
            },
            status_code=500
        )
    except Exception as e:
        import sys
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"Unexpected error at line {exc_tb.tb_lineno}: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"An unexpected error occurred (line {exc_tb.tb_lineno}). Please try again later."
            },
            status_code=500
        )

@app.get("/auth/user")
async def get_user(auth = Depends(require_auth)):
    if not auth["authenticated"]:
        return JSONResponse(content={"authenticated": False, "message": auth["message"]})
    user = auth["user"]
    return JSONResponse(content={
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email_addresses[0].email_address,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    })

@app.get("/alerts")
async def alerts(request: Request, user = Depends(get_auth_user)):
    """
    Endpoint to display user's currency alerts
    """
    try:
        # Debug logging
        print("User object:", user)
        if user:
            print("User ID:", getattr(user, 'id', None))
            print("User email addresses:", getattr(user, 'email_addresses', None))
            if hasattr(user, 'email_addresses') and user.email_addresses:
                print("Primary email:", user.email_addresses[0].email_address)
            print("User first name:", getattr(user, 'first_name', None))
            print("User last name:", getattr(user, 'last_name', None))
        else:
            print("No user object received")

        # Get user email from Clerk user object
        user_email = None
        if user and hasattr(user, 'email_addresses') and user.email_addresses:
            user_email = user.email_addresses[0].email_address
            alerts_list = list(alerts_collection.find({"email": user_email}).sort("created_at", -1))
        else:
            print("User email not found. Showing all alerts. Please sign in to see only your alerts.")
            alerts_list = []
            
        # Convert ObjectId to string for each alert
        for alert in alerts_list:
            alert["_id"] = str(alert["_id"])
        
        return templates.TemplateResponse(
            "alerts.html",
            {
                "request": request,
                "alerts": alerts_list,
                "user_email": user_email  # Pass to template so we can show console warning if None
            }
        )
    except Exception as e:
        print(f"Error fetching alerts: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Unable to fetch alerts. Please try again later."
            },
            status_code=500
        )

@app.post("/delete")
async def delete_alerts(request: Request):
    """
    Endpoint to delete selected alerts
    """
    try:
        # Parse the request body
        data = await request.json()
        ids = data.get('ids', [])
        
        if not ids:
            raise HTTPException(status_code=400, detail="No alert IDs provided")
        
        # Convert string IDs to ObjectId and delete the alerts
        from bson.objectid import ObjectId
        result = alerts_collection.delete_many({
            "_id": {"$in": [ObjectId(id) for id in ids]}
        })
        
        if result.deleted_count > 0:
            return JSONResponse(content={
                "success": True,
                "message": f"Successfully deleted {result.deleted_count} alert(s)"
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "No alerts were deleted"
            }, status_code=404)
            
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "message": str(e)
        }, status_code=500)