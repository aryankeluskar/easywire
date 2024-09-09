FROM python:3.9


WORKDIR /

COPY ./requirements.txt /docker/requirements.txt

RUN pip install --no-cache-dir --upgrade -r docker/requirements.txt

COPY api.py /docker/api.py

COPY ./templates /docker/templates
COPY ./data /docker/data

CMD ["fastapi", "run", "/docker/api.py", "--host", "0.0.0.0", "--port", "3000"]