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
from datetime import datetime
import re
from pymongo import MongoClient
import socket

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
    
    # Store the alert in MongoDB
    alert_data = {
        "amount": float(amount),
        "from_currency": from_currency,
        "to_currency": to_currency,
        "target_date": datetime.strptime(date, '%Y-%m-%d'),
        "email": email,
        "created_at": datetime.utcnow()
    }
    alerts_collection.insert_one(alert_data)
    
    # Redirect to success page with the selected currencies
    return RedirectResponse(url=f"/success?from_curr={from_currency}&to_curr={to_currency}", status_code=303)

# @app.get("/graph/usd_inr_all")
# async def graph_usd_inr_all():
#     return FileResponse("data/usd_inr_all.png")

# @app.get("/favicon.ico")
# async def favicon():
#     return FileResponse("favicon.ico")

@app.get("/success")
async def success(request: Request, from_curr: str, to_curr: str):
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

        api_url = f"https://ewb.aryankeluskar.com/generate_data"
        params = {
            "from_currency": from_curr,
            "to_currency": to_curr,
            "password": os.getenv('API_PASSWORD')
        }
        
        print(f"Making request to {api_url} with params: {from_curr}, {to_curr}")
        start_time = datetime.now()
        
        response = requests.get(api_url, params=params, timeout=30)
        
        request_time = (datetime.now() - start_time).total_seconds()
        print(f"Request completed in {request_time} seconds")
        
        # Check if request was successful
        if response.status_code == 429:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Too many requests. Please try again in a few minutes."
                },
                status_code=429
            )
        
        response.raise_for_status()
        
        try:
            forex_data = response.json()
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
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Data parsing error: {str(e)}")
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Unable to process forex data. Please try again later."
                },
                status_code=500
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