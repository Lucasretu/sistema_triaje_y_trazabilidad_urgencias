# Funciones de lógica de colas y boxes en Redis
import json
import time
import redis

from config import REDIS_HOST, REDIS_PORT, REDIS_DB

# Define el nombre de la cola de espera.
QUEUE_KEY = "urgencias:cola_espera"

# Define los cinco boxes disponibles.
BOXES = [f"box:{i}" for i in range(1, 6)]

# Crea la conexión con Redis.
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Comprueba la conexión con Redis y prepara los cinco boxes
def initialize_boxes():
    # Comprueba que Redis está disponible.
    redis_client.ping()

    # Crea los hashes de los boxes sin modificar los existentes.
    for box in BOXES:
        redis_client.hsetnx(box, "id_episodio", "")
        redis_client.hsetnx(box, "hora_entrada", "")

# Calcula el límite máximo de atención a un paciente.
def calculate_attention_limit(paciente):
    # Obtiene los datos de admisión y triaje del paciente.
    admision = paciente.get("datos_admision", {})
    triaje = paciente.get("datos_triaje", {})

    # Extrae el momento de llegada y el tiempo máx de espera
    llegada = admision.get("timestamp_llegada")
    espera = triaje.get("tiempo_max_espera_min")

    # Comprueba que los datos son números
    if isinstance(llegada, bool) or not isinstance(llegada, (int, float)):
        raise ValueError("El timestamp de llegada no es válido.")

    if isinstance(espera, bool) or not isinstance(espera, (int, float)) or espera < 0:
        raise ValueError("El tiempo máximo de espera no es válido.")

    # Calcula la fecha límite de atención expresada en segundos.
    return float(llegada) + float(espera) * 60

# Busca si un episodio ya está ocupando un box y devuelve el nombre del box si lo encuentra.
def find_patient_box(id_episodio):
    # Recorre los cinco boxes para localizar al paciente.
    for box in BOXES:
        if redis_client.hget(box, "id_episodio") == id_episodio:
            return box
    return None

# Asifna pacientes de la cola a boxes disponibles y devuelve la lista de boxes ocupados.
def assign_patients_to_boxes(preferred_box=None):
    # Guarda las nuevas asignaciones realizadas
    assignments = []

    while True:
        # Da prioridad al box que acaba de quedar libre.
        if preferred_box and not redis_client.hget(preferred_box, "id_episodio"):
            free_box = preferred_box
            preferred_box = None
        else:
            # Busca el primer box que esté libre.
            free_box = next(
                (box for box in BOXES if not redis_client.hget(box, "id_episodio")),
                None
            )

        # Finaliza si no hay boxes libres.
        if free_box is None:
            break

        # Extrae el paciente de la cola con el score más bajo
        next_patient = redis_client.zpopmin(QUEUE_KEY, 1)

        # Termina si no hay pacientes en la cola
        if not next_patient:
            break

        # Obtiene el id y el score del paciente
        id_episodio, score = next_patient[0]

        # Omite entradas de cola que no tengan datos asociados.
        if not redis_client.exists(f"paciente:{id_episodio}"):
            continue

        # Registra el paciente y la hora de entrada en el box.
        hora_entrada = time.time()
        redis_client.hset(free_box, mapping={"id_episodio": id_episodio, "hora_entrada": hora_entrada})

        # Guarda información de la asignación realizada.
        assignments.append({"box": free_box, "id_episodio": id_episodio, "hora_entrada": hora_entrada, "score": score})

    # Devuelve las asignaciones realizadas.
    return assignments

# Guarda un nuevo paciente en el Redis y lo añade a la cola de espera.
def add_patient_to_queue(paciente):
    # Comprueba que haya un id
    id_episodio = paciente.get("id_episodio")

    if not isinstance(id_episodio, str) or not id_episodio:
        raise ValueError("El identificador del episodio no es válido.")

    # Comprueba que Redis esté conectado y los boxes disponibles.
    initialize_boxes()

    # Calcula la prioridad de atención del paciente.
    score = calculate_attention_limit(paciente)

    # Guarda los datos completos del paciente en Redis.
    patient_key = f"paciente:{id_episodio}"
    pat_json = json.dumps(paciente, ensure_ascii=False)

    # Actualiza los datos sin volver a la cola a un paciente ya asignado.
    if find_patient_box(id_episodio):
        redis_client.set(patient_key, pat_json)
        return []

    # Guarda los datos y añade el episodio a la cola ordenada.
    with redis_client.pipeline() as pipe:
        pipe.set(patient_key, pat_json)
        pipe.zadd(QUEUE_KEY, {id_episodio: score})
        pipe.execute()

    # Ocupa los boxes libres con los pacientes prioritarios.
    return assign_patients_to_boxes()

# Prepara el documento de un paciente que ha recibido el alta.
def prepare_discharge_document(alta):
    # Extrae el identificador del episodio.
    id_episodio = alta.get("id_episodio")

    # Comprueba que exista un identificador válido.
    if not isinstance(id_episodio, str) or not id_episodio:
        print("El alta no contiene un identificador válido.")
        return None

    # Recupera los datos del paciente almacenados en Redis.
    pat_json = redis_client.get(f"paciente:{id_episodio}")

    # Comprueba que el episodio esté registrado en Redis.
    if pat_json is None:
        print(f"No se encontraron datos del episodio {id_episodio}.")
        return None

    # Convierte los datos almacenados en un diccionario.
    try:
        document = json.loads(pat_json)
    except ValueError:
        print(f"No se pudieron interpretar los datos del episodio {id_episodio}.")
        return None

    # Añade los datos definitivos del alta al documento.
    document["datos_alta"] = alta

    # Devuelve el documento preparado para MongoDB.
    return document


# Libera el box del paciente dado de alta y elimina sus datos de Redis.
def complete_discharge(id_episodio):
    # Comprueba que el identificador del episodio sea válido.
    if not isinstance(id_episodio, str) or not id_episodio:
        raise ValueError("El identificador del episodio no es válido.")

    # Busca el box que ocupa el paciente.
    occupied_box = find_patient_box(id_episodio)

    # Libera el box si el paciente estaba asignado.
    if occupied_box:
        redis_client.hset(occupied_box, mapping={"id_episodio": "", "hora_entrada": ""})

    # Elimina el episodio de la cola por si todavía estaba esperando.
    redis_client.zrem(QUEUE_KEY, id_episodio)

    # Elimina los datos del paciente de Redis.
    redis_client.delete(f"paciente:{id_episodio}")

    # Asigna el siguiente paciente prioritario al box que se ha liberado.
    assignments = assign_patients_to_boxes(occupied_box)

    # Devuelve el box liberado y las nuevas asignaciones.
    return {"box_liberado": occupied_box, "asignaciones": assignments}


# Comprueba la conexión e inicializa los boxes al ejecutar este archivo.
if __name__ == "__main__":
    initialize_boxes()
    print("Conexión con Redis correcta. Los cinco boxes están preparados.")