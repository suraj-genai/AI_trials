FROM python:3.12-slim

WORKDIR /app

COPY BackEnd/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY BackEnd ./BackEnd/

COPY FrontEnd ./FrontEnd/

EXPOSE 7860

WORKDIR /app/BackEnd

CMD ["python", "app.py"]