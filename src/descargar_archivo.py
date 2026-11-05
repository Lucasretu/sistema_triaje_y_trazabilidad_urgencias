import time
from pathlib import Path
import requests
from config import DOWNLOAD_BASE_URL, UPDATES_API_URL

# Método para descargar los ficheros desde la red
def download(file_name):
    # Servidor
    site = DOWNLOAD_BASE_URL
    
    # Ruta del archivo a descargar
    url = site + file_name
    
    # Nombre y dónde con el que quiero descargar el archivo. (Mismo que el recibido)
    output_path = Path(__file__).resolve().parent / "./data" / Path(file_name).name
    # Crea la carpeta de destino si todavía no existe.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Captura errores HTTP o de conexión de la petición.
    try:
        # Solicita el archivo con tiempos límite y sin cargarlo entero en memoria.
        with requests.get(url, stream=True, timeout=(5, 30)) as response:
            # Lanza un error si el servidor responde con un estado HTTP fallido.
            response.raise_for_status()

            # Abre el destino en modo escritura.
            with output_path.open("wb") as file:
                # Lee la respuesta en bloques de 1 MB.
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    # Omite los bloques vacíos.
                    if chunk:
                        # Escribe cada bloque antes de pedir el siguiente.
                        file.write(chunk)
    
    # Atiende errores de red, timeout o estado HTTP fallido.
    except requests.RequestException as error: 
        # Informa del fallo y conserva la causa original. 
        raise RuntimeError(f"No se pudo descargar {file_name}: {error}") from error

    
# Método que leerá la API cada x tiempo para comprobar si hay novedades
def check_updates():
    # Servidor (json)
    site = UPDATES_API_URL

    # Captura los errores de conexión y de respuesta HTTP.
    try:
        # Hace la petición y evita esperar indefinidamente.
        response = requests.get(site, timeout=10)
        # Detecta respuestas HTTP fallidas. 
        response.raise_for_status()

    # Atiende errores.
    except requests.RequestException as error:
        # Muestra el motivo del fallo.
        print(f"Error al consultar la API: {error}")
        # Termina para volver a intentarlo.
        return
    
    # Valida por separado que la respuesta contenga JSON válido.
    try:
        # Convierte el JSON recibido en datos de Python.
        datos = response.json()

    # Atiende respuestas con JSON mal formado.
    except ValueError as error:
        # Informa del problema con el contenido.
        print(f"La API devolvió un JSON inválido: {error}")
        # Termina esta consulta.
        return


# Actualizar la API cada 5 segundos
while True:
    check_updates()
    time.sleep(5)