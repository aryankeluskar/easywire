from typing import Annotated

from fastapi import FastAPI, Request, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd

from fastapi.templating import Jinja2Templates
from math import floor

from prophet.serialize import model_from_json

import datetime
import os

from dotenv import load_dotenv

load_dotenv()

TEMPLATES = Jinja2Templates(directory="/")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

templates_dir = os.path.join(os.path.dirname(__file__), "templates", "homepage_files")
print(templates_dir)
app.mount(
    "/homepage_files",
    StaticFiles(
        directory=templates_dir,
    ),
    name="homepage_files",
)
app.mount(
    "/templates",
    StaticFiles(
        directory=os.path.join(os.path.dirname(__file__), "templates"),
    ),
    name="templates",
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
        directory=os.path.join(
            os.path.dirname(__file__),
            "data",
        )
    ),
    name="data",
)


templates = Jinja2Templates(directory="/")


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
    return FileResponse("./docker/templates/home.html")


@app.get("/sucess", response_class=HTMLResponse)
async def success_demo(request: Request):
    return FileResponse("./docker/templates/success_trial.html")


@app.post("/success", response_class=HTMLResponse)
async def data(
    amount: Annotated[str, Form()] = "",
    date: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    request: Request = None,
):
    # print("data")
    print("amount: " + amount)
    print("date: " + date)
    print("email: " + email)

    _res = await calculate(date, float(amount), email)
    savings = _res[0]
    opt_date = _res[1]

    print("opt_date: " + opt_date)
    opt_date = opt_date[2:12]
    print("opt_date: " + opt_date)

    # opt_date is now '2024-09-20T00:00:00.000000000' convert to words like '20th September 2024'
    opt_date = datetime.datetime.strptime(opt_date, "%Y-%m-%d")
    opt_date = opt_date.strftime("%d %B %Y")

    savings = round(savings, 3)

    print("savings: " + str(savings))
    print("optimal date: " + str(opt_date))

    return TEMPLATES.TemplateResponse(
        name="/success.html",
        context={
            "request": request,
            "savings": savings,
            "opt_date": opt_date,
        },
    )

    # return ("../success.html?savings=" + str(savings) + "&opt_date=" + str(opt_date))


async def calculate(date: str, amount: float, email: str):
    r"""
    Function to do the main stuff. Uses prophet to predict the exchange rate. Sentiment analysis is on a separate dashboard for now.
    """

    today = str(datetime.datetime.now())[:11]

    print("date: " + date)
    print("today: " + today)

    with open("./docker/data/serialized_model.json", "r") as fin:
        m = model_from_json(fin.read())

    future = m.make_future_dataframe(periods=1826)
    future["cap"] = 8.5
    fcst = m.predict(future)

    # fcst = pd.read_csv("./docker/data/fcst.csv")

    fy2024 = fcst[(fcst["ds"] > today) & (fcst["ds"] < date)][["ds", "yhat"]]

    # get lowest in fy2024 along with date
    low = fy2024[fy2024["yhat"] == fy2024["yhat"].min()]

    # get max in fy2024 along with date
    high = fy2024[fy2024["yhat"] == fy2024["yhat"].max()]

    print(low)
    print(high)

    low_p = floor(list(low["yhat"])[0])
    high_p = list(high["yhat"])[0]

    amt = amount
    print("Current Amount (USD): ", amt)

    # print(f"Amount on {str(low['ds'].values[0])[:10]}: INR", amt*low_p)
    # print("Saving: INR", (amt*high_p - amt*low_p))

    # print(((high_p-low_p)/low_p)*100)
    savings = amt * high_p - amt * low_p
    final_date = str(low["ds"].values)

    # create a graph of USD to INR only from today to date. make sure the scaling is small so the changes are visible
    import matplotlib.pyplot as plt
    
    # remove year from date
    fy2024["ds"] = fy2024["ds"].apply(lambda x: str(x)[5:10])
    
    plt.plot(fy2024["ds"], fy2024["yhat"], color="blue")
    
    # remove x-axis intervals
    plt.xticks([])
    
    plt.xlabel("Date")
    plt.ylabel("USD to INR")
    plt.savefig("./docker/data/prediction.png")

    return (savings, final_date)

@app.get("/graph/prediction")
async def graph_prediction():
    return FileResponse("./docker/data/prediction.png")

@app.get("/graph/usd_inr_all")
async def graph_usd_inr_all():
    return FileResponse("./docker/data/usd_inr_all.png")

    # import pandas as pd
    # from prophet import Prophet

    # df = pd.read_csv("data/usd_inr.csv")
    # print("retrieved usd to inr data")
    # df.columns = ["ds", "y"]

    # # remove any NaN or other values
    # df = df.dropna()

    # # remove values in Y where there is a .
    # df = df[df["y"] != "."]
    # df.head()

    # import matplotlib.pyplot as plt

    # plt.plot(df["ds"], df["y"])
    # print("retrieved usd to inr data")

    # m = Prophet()
    # m.fit(df)

    # future = m.make_future_dataframe(periods=365)
    # forecast = m.predict(future)
    # fig2 = m.plot_components(forecast)
    # print(fig2)
    # print(type(fig2))
    # fig2.savefig("data/usd_inr_all.png")
    # return FileResponse("data/usd_inr_all.png")
