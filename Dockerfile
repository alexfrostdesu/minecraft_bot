FROM python:3.10-slim

ENV BOT_TOKEN $BOT_TOKEN

ENV SERVER_IP $SERVER_IP

COPY app.py Pipfile Pipfile.lock app/
WORKDIR app/

RUN pip install pipenv && pipenv install --deploy --system

CMD ["python", "-u ./app.py"]