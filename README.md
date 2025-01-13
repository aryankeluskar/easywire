<p align="center">
  <a href="https://github.com/edcomposer">
    <h2 align="center">EasyWire - Optimize Global Transactions 🌎</h2>
  </a>
</p>

<p align="center">
  <img style=" width: 350px" src="https://raw.githubusercontent.com/aryankeluskar/easywire/master/easywire-tw.jpeg" alt="Tweet for EasyWire">
</p>


## 🔍 Monitoring System

The monitoring system continuously tracks exchange rates and sends notifications when optimal rates are detected. It uses Alpha Vantage API for real-time forex data and implements rate limiting to stay within API constraints.

### Monitoring Logs

Each monitoring job execution is logged with the following structure:

```json
{
    "timestamp": "<UTC timestamp when job started>",
    "status": "<completed|error>",
    "message": "<descriptive message>",
    "alerts_processed": "<number of alerts processed>",
    "results": [
        {
            "alert_id": "<alert_id>",
            "status": "<notification_sent|rate_not_optimal|error>",
            "current_rate": "<rate>",
            "error": "<error message if status is error>"
        }
    ],
    "duration_seconds": "<execution time in seconds>"
}
```

### Features

- **Rate Limiting**: Implements a sliding window rate limiter for Alpha Vantage API (5 calls per minute)
- **Lock Mechanism**: Prevents multiple monitoring processes from running simultaneously
- **Historical Data**: Maintains 7-day rate history for trend analysis
- **Sentiment Analysis**: Analyzes news sentiment to improve rate optimization decisions
- **Email Notifications**: Sends HTML-formatted alerts when optimal rates are detected
- **Error Handling**: Comprehensive error handling and logging for debugging

### Optimization Logic

Rate is considered optimal when either:
1. Current rate is better than 7-day average by more than 1 standard deviation
2. Rate is moderately good (>0.5 std dev better than average) AND news sentiment is positive




## 🚀 Quickstart

### 1. Generate a repo using this template

Use `git clone`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env` file

Copy the `.env.example` file to `.env` and fill in the values.

```config
# API Configuration
# Required: Contact easywire@aryankeluskar.com for backend API credentials
API_PASSWORD=your_api_password_here

# Clerk Authentication Configuration
# Required: Sign up at https://clerk.dev to obtain credentials
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key_here 
CLERK_SECRET_KEY=your_clerk_secret_key_here
```



### 4. Start the app

```bash
python main.py
```

This will start the app on [http://localhost:8000](http://localhost:8000).


## 🌄 Inspiration
- conceptualized and developed at [buildspace nights & weekends s5](https://buildspace.so/)