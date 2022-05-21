FROM python:3.10-slim

COPY app.py Pipfile Pipfile.lock app/
WORKDIR app/

RUN pip install pipenv && pipenv install --deploy --system

CMD ["python", "./app.py"]