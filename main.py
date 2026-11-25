# Scrip principal de la aplicación1

import time
from threading import Thread, Event

from src.urgencias_worker import check_updates, mongo_client
from src.triage_redis import initialize_boxes, redis_client
from src.etl_historico import main_1 as etl_main
from src.etl_historico import main_2 as mongo_main
from src.consultas import mostrar_consultas

# Evento para indicar al worker cuándo debe detenerse.
parar_worker = Event()

# Variable para controlar el hilo del worker.
worker_thread = None

# Ejecuta las consultas periódicas a la API.
def nuevos_datos():
    while not parar_worker.is_set():
        try:
            check_updates()
        except Exception as e:
            print(f"Error al consultar la API: {e}")

        # Espera cinco segundos antes de volver a consultar.
        parar_worker.wait(5)

# Inicia el procesamiento en tiempo real.
def iniciar_worker():
    global worker_thread

    if worker_thread is not None and worker_thread.is_alive():
        print("El procesamiento en tiempo real ya está iniciado.")
        return

    try:
        initialize_boxes()
        mongo_client.admin.command("ping")

        parar_worker.clear()

        worker_thread = Thread(target=nuevos_datos, daemon=True)
        worker_thread.start()

        print("Procesamiento en tiempo real iniciado.")

    except Exception as e:
        print(f"No se pudo iniciar el procesamiento: {e}")

# Detiene el procesamiento en tiempo real.
def detener_worker():
    if worker_thread is not None and worker_thread.is_alive():
        parar_worker.set()
        worker_thread.join(timeout=12)
        print("Procesamiento en tiempo real detenido.")
    else:
        print("El procesamiento en tiempo real no está iniciado.")

# Menú principal.
def menu_principal():
    print("Iniciando la aplicación...")
    time.sleep(1)

    while True:
        print()
        print("Seleccione una opción:")
        print("1. Exportacion de historico a JSON")
        print("2. Insercion del JSON en MongoDB")
        print("3. Consulta de datos en MongoDB")
        print("4. Iniciar procesamiento en tiempo real")
        print("5. Salir")
        print()

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            # Llamamos a la funcion principal del script del ETL para limpiar los datos y exportarlos a JSON
            try:
                etl_main()
                print("Exportación de historico a JSON completada.")
            except Exception as e:
                print(f"No se pudo exportar el histórico: {e}")
        elif opcion == "2":
            # Llamamos a la funcion principal del script del ETL para insertar el JSON en MongoDB
            try:
                mongo_main()
                print("Inserción del JSON en MongoDB completada.")
            except Exception as e:
                print(f"No se pudo insertar el histórico en MongoDB: {e}")
        elif opcion == "3":
            # Muestra las consultas analíticas.
            try:
                mostrar_consultas()
            except Exception as e:
                print(f"No se pudieron mostrar las consultas: {e}")
        elif opcion == "4":
            iniciar_worker()
        elif opcion == "5":
            print("Saliendo del programa...")
            break
        else:
            print("Opción inválida. Por favor, ingrese un número válido.")

# Punto de entrada de la aplicación.
if __name__ == "__main__":
    try:
        menu_principal()

    except KeyboardInterrupt:
        print("\nInterrupción del programa.")

    finally:
        detener_worker()
        mongo_client.close()
        redis_client.close()
        print("Conexiones cerradas.")