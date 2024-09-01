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
app.mount(
    "/css",
    StaticFiles(
        directory=templates_dir,
    ),
    name="css",
)
app.mount(
    "/data",
    StaticFiles(
        directory=templates_dir,
    ),
    name="data",
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
    # print("data")
    print("amount: " + amount)
    print("date: " + date)
    print("email: " + email)
    
    _res = await calculate(date, float(amount), email)
    savings = _res[0]
    final_date = _res[1]

    # redirect to /success
    return FileResponse("templates/success.html?savings=" + str(savings) + "&final_date=" + final_date)


@app.get("/graph/usd_inr_all")
async def graph_usd_inr_all():
    return FileResponse("data/usd_inr_all.png")

    import pandas as pd
    from prophet import Prophet
    df = pd.read_csv('data/usd_inr.csv')
    print("retrieved usd to inr data")
    df.columns = ['ds', 'y']

    # remove any NaN or other values
    df = df.dropna()

    # remove values in Y where there is a .
    df = df[df['y'] != '.']
    df.head()
    
    import matplotlib.pyplot as plt
    plt.plot(df['ds'], df['y'])
    print("retrieved usd to inr data")

    m = Prophet()
    m.fit(df)

    future = m.make_future_dataframe(periods=365)
    forecast = m.predict(future)
    fig2 = m.plot_components(forecast)
    print(fig2)
    print(type(fig2))
    fig2.savefig('data/usd_inr_all.png')
    return FileResponse("data/usd_inr_all.png")