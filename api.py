import json
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

templates_dir = os.path.join(os.path.dirname(__file__), "templates", "homepage_files")
app.mount(
    "/homepage_files",
    StaticFiles(
        directory=templates_dir,
    ),
    name="homepage_files",
)

@app.get("/")
async def root():
    r"""
    ### Root Endpoint
    A function that serves the root endpoint of the API. It returns a FileResponse object that
    represents the "index.html" file located in the "templates" directory. This function is
    decorated with the `@app.get("/")` decorator, which means it will handle GET requests to the
    root URL ("/").
    ---
    Returns:
        FileResponse: A FileResponse object representing the "index.html" file.
    """
    # print list of files in templates directory
    print(os.listdir())
    return FileResponse("templates/home.html")

@app.post("/data")
async def data(
    amount: Annotated[str, Form()] = "",
    date: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
):
    print("data")
    print(amount, date, email)
    return {"success": True}