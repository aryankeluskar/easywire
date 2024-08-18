import uvicorn
import os

if os.getenv("PORT") is None:
    API_PORT = 8000
else:
    API_PORT = int(os.getenv("PORT"))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=API_PORT, reload=True)
