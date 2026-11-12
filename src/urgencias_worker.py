# Agente de polling continuo contra la API
import time
import requests
import os

from pymongo import MongoClient
from config import UPDATES_API_URL
from triage_redis import (initialize_boxes, add_patient_to_queue, prepare_discharge_document, complete_discharge)

# Configura la conexión con MongoDB.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["hospital_db"]
collection = mongo_db["episodios_urgencias"]

# Consultar la API cada 5 segundos 
def get_updates():
    try:
        # Solicita las novedades al servidor.
        response = requests.get(UPDATES_API_URL, timeout=10)
        response.raise_for_status()

        # Convierte la respuesta en un diccionario.
        datos = response.json()

        # Comprueba que la respuesta tenga el formato esperado.
        if not isinstance(datos, dict):
            raise ValueError("La respuesta de la API no es válida.")

        # Comprueba que las listas de novedades sean correctas.
        if not isinstance(datos.get("nuevos_ingresos", []), list):
            raise ValueError("La lista de ingresos no es válida.")

        if not isinstance(datos.get("pacientes_alta", []), list):
            raise ValueError("La lista de altas no es válida.")

        return datos

    except (requests.RequestException, ValueError) as error:
        print(f"Error al consultar la API: {error}")
        return None

# Procesa los nuevos ingresos y los incorpora a la cola de Redis.
def process_new_patients(patients):
    for patient in patients:
        try:
            # Comprueba que el ingreso tenga el formato correcto.
            if not isinstance(patient, dict):
                print("El ingreso no tiene el formato esperado:", patient)
                continue
            
            # Añade el paciente a la cola de Redis y lo asigna a un box si hay alguno libre e informa del ingreso.
            assignments = add_patient_to_queue(patient)
            print(f"Nuevo ingreso procesado: {patient['id_episodio']}")
            
             # Informa de los boxes asignados.
            for asignacion in assignments:
                print(f"Paciente {asignacion['id_episodio']} "f"asignado a {asignacion['box']}")
            
        except (ValueError, KeyError) as error:
            print(f"Error al procesar un ingreso: {error}")
            
# Guarda en MongoDB los episodios que reciben el alta y los elimina de Redis.
def process_discharges(discharges):
    for alta in discharges:
        try:
            # Comprueba que el alta tenga el formato esperado.
            if not isinstance(alta, dict):
                continue

            # Recupera los datos completos del paciente desde Redis.
            documento = prepare_discharge_document(alta)

            # No continúa si no se encuentran los datos del episodio.
            if documento is None:
                continue

            # Guarda o actualiza el episodio en MongoDB.
            collection.update_one({"id_episodio": alta["id_episodio"]}, {"$set": documento}, upsert=True)

            # Elimina el episodio de Redis después de guardarlo en MongoDB.
            resultado = complete_discharge(alta["id_episodio"])

            # Informa del alta y del box liberado.
            print(f"Alta guardada en MongoDB: {alta['id_episodio']}")

            if resultado["box_liberado"]:
                print(f"Box liberado: {resultado['box_liberado']}")

            # Informa de los pacientes asignados a los boxes disponibles.
            for asignacion in resultado["asignaciones"]:
                print(
                    f"Paciente {asignacion['id_episodio']} "
                    f"asignado a {asignacion['box']}"
                )

        except (ValueError, KeyError) as error:
            print(f"Error al procesar un alta: {error}")
        except Exception as error:
            print(f"Error al guardar el alta en MongoDB: {error}")
            
# Ejecuta una consulta a la API y procesa sus novedades.
def check_updates():
    # Consulta la API para obtener los nuevos ingresos y altas.
    datos = get_updates()

    # No continúa si no se han recibido datos válidos.
    if datos is None:
        return

    # Procesa los nuevos ingresos y las altas recibidas.
    process_new_patients(datos.get("nuevos_ingresos", []))
    process_discharges(datos.get("pacientes_alta", []))
    
# Inicia el agente y consulta la API cada cinco segundos.
if __name__ == "__main__":
    try:
        # Comprueba las conexiones e inicializa los boxes.
        initialize_boxes()
        mongo_client.admin.command("ping")

        print("Conexión con Redis y MongoDB correcta.")
        print("Agente de urgencias iniciado.")

        # Mantiene el sondeo continuo de la API.
        while True:
            check_updates()
            time.sleep(5)

    except KeyboardInterrupt:
        print("Agente de urgencias detenido.")

    except Exception as error:
        print(f"Error al iniciar el agente: {error}")

    finally:
        # Cierra la conexión con MongoDB.
        mongo_client.close()