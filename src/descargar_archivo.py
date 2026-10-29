from urllib.request import urlopen
from pathlib import Path
import requests

# Método para descargar los ficheros desde la red
def download(file_name):
    # Servidor
    site = 'http://10.201.59.248:8088/'
    
    # Ruta del archivo a descargar
    url = site + file_name
    
    # Llamada al servidor para descargar el archivo
    r = urlopen(url)
    
    # Nombre y dónde con el que quiero descargar el archivo. (Mismo que el recibido)
    output_path = Path(__file__).resolve().parent / "./data" / Path(file_name).name
    with open(output_path, 'wb') as f:
        f.write(r.read())
    r.close()

# Método que leerá la API cada x tiempo para comprobar si hay novedades
def check_updates():
    # Servidor (json)
    site = 'http://10.201.59.248:28000/api/v1/urgencias/novedades'
    
    # Realizar la petición GET
    response = requests.get(site)

    # Verificar que la petición fue exitosa (código 200)
    if response.status_code == 200:
        # Convertir el contenido JSON en un diccionario de Python
        datos = response.json()
        print("Datos recibidos:")
        print(datos)
        print("Título:", datos.get("title"))
    else:
        print(f"Error en la petición: {response.status_code}")