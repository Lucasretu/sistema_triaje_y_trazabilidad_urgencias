FROM python:3.12-slim

#Recomendable cambiar a un directorio de trabajo más específico para la aplicación
WORKDIR /app

#Habria que revisar las versiones pero de momento asi esta bien
COPY requirements.txt .

#Se instalan los requerimientos
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]