import json
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import requests
from clerk_backend_api import Clerk
from datetime import datetime, timedelta
import re
from pymongo import MongoClient
import socket
import hashlib

load_dotenv()

# MongoDB Connection
MONGO_CONNECTION_STRING = os.getenv('MONGO_CONNECTION_STRING_P1') + os.getenv('MONGODB_USER_PWD') + os.getenv('MONGO_CONNECTION_STRING_P2')
mongo_client = MongoClient(MONGO_CONNECTION_STRING)
db = mongo_client['easywire']
alerts_collection = db['alerts']

# Initialize Clerk
clerk = Clerk(bearer_auth=os.getenv('CLERK_SECRET_KEY'))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Clerk authentication middleware
async def get_auth_user(request: Request):
    session_token = request.cookies.get('__session')
    if not session_token:
        return None
    try:
        session = clerk.sessions.verify_session(session_token)
        user = clerk.users.get(session.user_id)
        return user
    except:
        return None

# Protected route dependency
async def require_auth(user = Depends(get_auth_user)):
    if not user:
        return {"authenticated": False, "message": "Please Sign In"}
    return {"authenticated": True, "user": user}

templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app.mount(
    "/templates",
    StaticFiles(
        directory=templates_dir,
    ),
    name="templates",
)

app.mount(
    "/homepage_files",
    StaticFiles(
        directory=templates_dir+"/homepage_files",
    ),
    name="homepage_files",
)

templates = Jinja2Templates(directory=templates_dir)

# Valid currency codes (common ones)
VALID_CURRENCIES = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'INR', 'NZD'}

@app.get("/")
async def root():
    r"""
    ### Root Endpoint
    A function that serves the root endpoint of the API. It returns a FileResponse object that
    represents the "home.html" file located in the "templates" directory. This function is
    decorated with the `@app.get("/")` decorator, which means it will handle GET requests to the
    root URL ("/").
    ---
    Returns:
        FileResponse: A FileResponse object representing the "home.html" file.
    """
    
    print(f"Serving template from: {os.path.join(templates_dir, 'home.html')}")

    return FileResponse(os.path.join(templates_dir, 'home.html'))


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
    """Helper function to fetch forex data from Alpha Vantage, GDP from World Bank API, and news from custom API"""
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    # Currency to country code mapping (for World Bank API)
    CURRENCY_TO_COUNTRY = {
        'USD': 'US',
        'EUR': 'EU',
        'GBP': 'GB',
        'JPY': 'JP',
        'AUD': 'AU',
        'CAD': 'CA',
        'CHF': 'CH',
        'CNY': 'CN',
        'INR': 'IN',
        'NZD': 'NZ'
    }
    
    # Fetch current exchange rate
    url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_currency}&to_currency={to_currency}&apikey={ALPHA_VANTAGE_API_KEY}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "Realtime Currency Exchange Rate" not in data:
            raise Exception("Failed to fetch forex data from Alpha Vantage")
        
        exchange_rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
        
        # Fetch historical data for predictions
        historical_url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={from_currency}&to_symbol={to_currency}&apikey={ALPHA_VANTAGE_API_KEY}"
        historical_response = requests.get(historical_url, timeout=30)
        historical_response.raise_for_status()
        historical_data = historical_response.json()
        
        if "Time Series FX (Daily)" not in historical_data:
            raise Exception("Failed to fetch historical forex data from Alpha Vantage")
            
        time_series = historical_data["Time Series FX (Daily)"]
        dates = sorted(time_series.keys(), reverse=True)
        
        # Calculate 52-week high and low
        high_52 = -float('inf')
        low_52 = float('inf')
        for date in dates[:252]:  # ~252 trading days in a year
            high_52 = max(high_52, float(time_series[date]["2. high"]))
            low_52 = min(low_52, float(time_series[date]["3. low"]))
        
        # Simple prediction based on 7-day trend
        rates_7d = [float(time_series[date]["4. close"]) for date in dates[:7]]
        trend = sum(rates_7d[i] - rates_7d[i+1] for i in range(len(rates_7d)-1)) / (len(rates_7d)-1)
        predicted_tomorrow = exchange_rate + trend

        # Fetch GDP data from World Bank API
        gdp_from = "N/A"
        gdp_to = "N/A"
        
        if from_currency in CURRENCY_TO_COUNTRY and to_currency in CURRENCY_TO_COUNTRY:
            from_country = CURRENCY_TO_COUNTRY[from_currency]
            to_country = CURRENCY_TO_COUNTRY[to_currency]
            
            # World Bank API endpoints
            wb_from_url = f"http://api.worldbank.org/v2/country/{from_country}/indicator/NY.GDP.MKTP.CD?format=json&per_page=1&mrnev=1"
            wb_to_url = f"http://api.worldbank.org/v2/country/{to_country}/indicator/NY.GDP.MKTP.CD?format=json&per_page=1&mrnev=1"
            
            try:
                # Fetch GDP for 'from' country
                wb_from_response = requests.get(wb_from_url, timeout=30)
                wb_from_data = wb_from_response.json()
                if len(wb_from_data) > 1 and wb_from_data[1] and len(wb_from_data[1]) > 0:
                    gdp_from = f"{(wb_from_data[1][0]['value'] / 1e12):.2f}T USD"
                
                # Fetch GDP for 'to' country
                wb_to_response = requests.get(wb_to_url, timeout=30)
                wb_to_data = wb_to_response.json()
                if len(wb_to_data) > 1 and wb_to_data[1] and len(wb_to_data[1]) > 0:
                    gdp_to = f"{(wb_to_data[1][0]['value'] / 1e12):.2f}T USD"
            except Exception as e:
                print(f"Error fetching GDP data: {str(e)}")
                # Continue with N/A values for GDP if there's an error

        # Fetch news from custom API
        news_url = "https://ewb.aryankeluskar.com/generate_data"
        news_response = requests.get(news_url, params={
            "from_currency": from_currency,
            "to_currency": to_currency,
            "password": os.getenv('API_PASSWORD')
        }, timeout=30)
        news_response.raise_for_status()
        news_data = news_response.json()
        
        return {
            "current_rate": str(exchange_rate),
            "opening_price": str(float(time_series[dates[0]]["1. open"])),
            "closing_price": str(float(time_series[dates[0]]["4. close"])),
            "high_52": str(high_52),
            "low_52": str(low_52),
            "predicted_change_tomorrow": trend > 0,
            "predicted_rate_tomorrow": str(predicted_tomorrow),
            "gdp_from_country": gdp_from,
            "gdp_to_country": gdp_to,
            "top5_news_articles": news_data.get("top5_news_articles", [])
        }
        
    except Exception as e:
        print(f"Error fetching forex data: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to fetch forex data. Please try again later.")

# @app.get("/graph/usd_inr_all")
# async def graph_usd_inr_all():
#     return FileResponse("data/usd_inr_all.png")

# @app.get("/favicon.ico")
# async def favicon():
#     return FileResponse("favicon.ico")

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
            
        # Add success message to the template
        return templates.TemplateResponse(
            "success.html",
            { 
                "from_curr": from_curr,
                "to_curr": to_curr,
                "request": request,
                "forex_data": forex_data,
                "success_message": "Successfully fetched forex data!"
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
        print(f"API Error: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Unable to fetch forex data. Please try again later."
            },
            status_code=500
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "An unexpected error occurred. Please try again later."
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
async def alerts(request: Request):
    """
    Endpoint to display user's currency alerts
    """
    try:
        # Get all alerts from MongoDB
        alerts_list = list(alerts_collection.find().sort("created_at", -1))
        
        # Convert ObjectId to string for each alert
        for alert in alerts_list:
            alert["_id"] = str(alert["_id"])
        
        return templates.TemplateResponse(
            "alerts.html",
            {
                "request": request,
                "alerts": alerts_list
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