import time
from pathlib import Path
from urllib.parse import urljoin
import requests
from config import DOWNLOAD_BASE_URL, UPDATES_API_URL

# Nombres de los dos archivos históricos disponibles en el servidor.
HISTORICAL_FILES = ("admisiones_historico.csv", "partes_clinicos.json")

# Método para descargar los ficheros desde la red
def download(file_name):
    # Rechaza nombres que no sean texto.
    if not isinstance(file_name, str):
        raise ValueError("El nombre del archivo debe ser texto.")

    # Solo permite descargar los dos archivos históricos del proyecto.
    if file_name not in HISTORICAL_FILES:
        raise ValueError("El archivo solicitado no está permitido.")

    # Servidor
    site = DOWNLOAD_BASE_URL
    
    # Ruta del archivo a descargar
    # Une correctamente la dirección del servidor con el nombre del archivo.
    url = urljoin(site.rstrip("/") + "/", file_name)
    
    # Nombre y dónde con el que quiero descargar el archivo. (Mismo que el recibido)
    output_path = Path(__file__).resolve().parent.parent / "data" / file_name
    # Evita descargar de nuevo un archivo que ya existe.
    if output_path.exists():
        return output_path
    # Crea la carpeta de destino si todavía no existe.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Evitar que una descarga incompleta deje un archivo defectuoso.
    temp_path = output_path.with_suffix(output_path.suffix + ".part")

    # Captura errores HTTP o de conexión de la petición.
    try:
        # Solicita el archivo con tiempos límite y sin cargarlo entero en memoria.
        with requests.get(url, stream=True, timeout=(5, 30)) as response:
            # Lanza un error si el servidor responde con un estado HTTP fallido.
            response.raise_for_status()

            # Abre el destino en modo escritura.
            with temp_path.open("wb") as file:
                # Lee la respuesta en bloques de 1 MB.
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    # Omite los bloques vacíos.
                    if chunk:
                        # Escribe cada bloque antes de pedir el siguiente.
                        file.write(chunk)
        
        # Descarga el archivo en un archivo temporal y luego lo renombra al nombre final.
        temp_path.replace(output_path)

    # Atiende errores de red, timeout o estado HTTP fallido.
    except (requests.RequestException, OSError) as error:
        # Elimina el archivo temporal si la descarga ha fallado.
        temp_path.unlink(missing_ok=True)
        # Informa del fallo y conserva la causa original. 
        raise RuntimeError(f"No se pudo descargar {file_name}: {error}") from error

    # Devuelve la ruta del archivo descargado.
    return output_path


# Descarga los dos archivos históricos y devuelve sus rutas locales.
def download_historical_files():
    return {name: download(name) for name in HISTORICAL_FILES}

    
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

        # Comprueba que la respuesta JSON sea un diccionario.
        if not isinstance(datos, dict):
            raise ValueError("La respuesta de la API no tiene el formato esperado.")

        # Comprueba que las novedades sean listas antes de recorrerlas.
        if not isinstance(datos.get("nuevos_ingresos", []), list) or not isinstance(datos.get("pacientes_alta", []), list):
            print("La API devuelve las listas de pacientes con un formato incorrecto.")
            return

    # Atiende respuestas con JSON mal formado.
    except ValueError as error:
        # Informa del problema con el contenido.
        print(f"La API devolvió un JSON inválido: {error}")
        # Termina esta consulta.
        return

    # Prepara las listas con los eventos que hayan superado la validación.
    nuevos_procesados = []
    altas_procesadas = []
    
    # Recorrer la lista con los nuevos pacientes y los pacientes dados de alta, si existen.
    for paciente in datos.get("nuevos_ingresos", []):
        if isinstance(paciente, dict):
            nuevo_ingreso = process_new_patient(paciente)
            if nuevo_ingreso:
                nuevos_procesados.append(nuevo_ingreso)
                print("Nuevo ingreso recibido:", nuevo_ingreso["id_episodio"])

    for paciente in datos.get("pacientes_alta", []):
        if isinstance(paciente, dict):
            alta = process_discharge(paciente)
            if alta:
                altas_procesadas.append(alta)
                print("Alta recibida:", alta["id_episodio"])

    # Devuelve los eventos preparados para que los utilice el worker.
    return {"nuevos_ingresos": nuevos_procesados, "pacientes_alta": altas_procesadas}


# Método para procesar los nuevos pacientes y descargar sus archivos.
def process_new_patient(paciente):
    # Extraer los datos del paciente y validar su estructura.
    id_episodio = paciente.get("id_episodio")
    admision = paciente.get("datos_admision", {})
    triaje = paciente.get("datos_triaje", {})

    # Valida que los datos del paciente sean correctos antes de continuar.
    if not id_episodio or not isinstance(admision, dict) or not isinstance(triaje, dict):
        print("Datos incorrectos en un nuevo ingreso.")
        return

    # Devuelve un diccionario con los datos del paciente para su posterior uso.
    return {"id_episodio": id_episodio, "datos_admision": admision, "datos_triaje": triaje}


# Método para procesar los pacientes dados de alta y descargar sus archivos.
def process_discharge(paciente):
    # Extraer los datos del paciente y validar su estructura.
    id_episodio = paciente.get("id_episodio")

    # Valida que los datos del paciente sean correctos antes de continuar.
    if not id_episodio:
        print("Datos incorrectos en un alta.")
        return

    # Devuelve un paciente con el id_episodio para su posterior uso.
    return paciente

# Actualizar la API cada 5 segundos
# If añadido para que se puedan importar las funciones sin que quede atrapado mirando la API
if __name__ == "__main__":
    while True:
        check_updates()
        time.sleep(5)