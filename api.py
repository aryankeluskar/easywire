import json
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

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

templates = Jinja2Templates(directory="templates")

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
    amount: Annotated[str, Form()] = "",
    from_currency: Annotated[str, Form()] = "",
    to_currency: Annotated[str, Form()] = "",
    date: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
):
    print("amount: " + amount)
    print("from_currency: " + from_currency)
    print("to_currency: " + to_currency)
    print("date: " + date)
    print("email: " + email)
    
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
    api_url = f"https://ewb.aryankeluskar.com/generate_data"
    params = {
        "from_currency": from_curr,
        "to_currency": to_curr,
        "password": os.getenv('API_PASSWORD')
    }
    
    response = requests.get(api_url, params=params)
    forex_data = response.json()
    
    print("received the following data from backend")
    print(forex_data)
    
    return templates.TemplateResponse(
        "success.html",
        { 
            "from_curr": from_curr,
            "to_curr": to_curr,
            "request": request,
            "forex_data": forex_data
        }
    )