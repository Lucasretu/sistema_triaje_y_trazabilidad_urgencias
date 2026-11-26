# Sistema de triaje y trazabilidad de urgencias

Proyecto de clase: sistema de triaje y trazabilidad de urgencias hospitalarias.

- **Histórico** (`data/admisiones_historico.csv` + `data/partes_clinicos.json`) → ETL → JSON → **MongoDB**.
- **Tiempo real** → API de novedades → **Redis** (cola + 5 boxes) → altas a **MongoDB**.
- **Consultas** analíticas sobre MongoDB.

IP del servidor: 10.201.59.241
Usuario y contraseña del servidor: `bd-admin` / `paso`

---

## 1. Arrancar y probar la aplicación (Docker)

Requisitos: Docker Desktop (o Docker Engine + Compose) arrancado.

1. Entra en la carpeta de Docker:

   ```bash
   cd docker
   ```

2. Construye y levanta todo (MongoDB, Redis, Mongo Express y la app):

   ```bash
   docker compose up -d --build
   ```

   El `--build` instala las dependencias (`pip install -r requirements.txt`) dentro de la imagen. Solo hace falta la primera vez o cuando cambie `requirements.txt`; después basta con `docker compose up -d`.

3. Entra al menú de la aplicación:

   ```bash
   docker attach python
   ```

   Para salir del menú **sin parar** el contenedor: `Ctrl+P` y luego `Ctrl+Q`.

4. En el menú, elige la **opción 1** para exportar el histórico limpio a `data/migracion_mongo.json`.

5. Elige la **opción 2** para insertar ese JSON en MongoDB (crea/actualiza `hospital_db.episodios_urgencias`). Debe mostrar unos **3418 documentos migrados**.

   > La opción 2 ya vuelve a generar el JSON por dentro, así que la 1 es opcional. Se pone primero para ver el paso a paso completo.

6. Elige la **opción 3** para ver las dos consultas:
   - estancia media por categoría patológica;
   - % domicilio vs ingreso en planta por grupo de edad.

7. Elige la **opción 4** para el procesamiento en tiempo real (consulta la API cada 5 segundos, llena los boxes de Redis y guarda las altas en Mongo).

   > Se necesita acceso a `http://10.201.59.248:28000/api/v1/urgencias/novedades`. Si no hay acceso, irá mostrando `Error al consultar la API` cada 5 s, pero **no se cae**.

8. Elige la **opción 5** para salir. Al salir, el contenedor `python` se para; se vuelve a arrancar con `docker compose up -d python`.

9. Para parar todos los servicios:

   ```bash
   docker compose down
   ```

   Los datos de Mongo se conservan en `docker/mongo_data`.

**Mongo Express** (ver la base en el navegador): <http://localhost:8081> — usuario `mongo`, contraseña `mongopassword`.

---

## 2. Ejecutar desde Windows (sin el contenedor de la app)

1. Levanta solo las bases de datos:

   ```bash
   cd docker
   docker compose up -d mongo redis
   cd ..
   ```

2. Instala las dependencias (solo la primera vez):

   ```bash
   pip install -r requirements.txt
   ```

3. Ejecuta la aplicación:

   ```bash
   python main.py
   ```

No tengas la opción 4 abierta a la vez en Windows y en el contenedor: serían dos workers compitiendo por los mismos boxes.

---

## 3. Opciones del menú

| Opción | Qué hace |
|---|---|
| 1 | Limpia el histórico y lo exporta a `data/migracion_mongo.json`. |
| 2 | Genera el JSON e inserta/actualiza los episodios en MongoDB. |
| 3 | Muestra las dos consultas analíticas sobre MongoDB. |
| 4 | Arranca el worker en tiempo real (API → Redis → MongoDB). |
| 5 | Detiene el worker y cierra las conexiones. |

---

## 4. Qué hace cada archivo de `src/`

**`config.py`**
Centraliza la configuración: URI de MongoDB, base de datos (`hospital_db`), colección (`episodios_urgencias`), y host/puerto/base de Redis. Lee los valores de variables de entorno y, si no existen, usa los de por defecto (`localhost`, `admin`/`adminpassword`). Así el mismo código funciona en local y dentro de Docker sin tocarlo.

**`etl_historico.py`**
Es el ETL del histórico (batch). `main_1()` lee el CSV y el JSON, normaliza textos y fechas, corrige frecuencias/tensiones/constantes imposibles, elimina duplicados y cruza ambos archivos por `id_episodio` + `sip_paciente`. Genera `data/migracion_mongo.json` separando ingresos y altas, y avisa de los episodios descartados por no tener parte clínico. `main_2()` repite la limpieza y hace `upsert` de cada episodio en MongoDB con `datos_admision`, `datos_triaje` y `datos_alta`.

**`urgencias_worker.py`**
Es el worker de tiempo real. `check_updates()` consulta la API, valida el JSON y procesa `nuevos_ingresos` y `pacientes_alta`. Los ingresos van a Redis y se asignan a boxes; las altas se guardan en MongoDB y después liberan el box. Si falla la API, un paciente o Mongo, lo avisa y sigue con el resto del lote (un fallo no corta todo). También incluye `download()` para descargar los históricos, aunque el menú actual usa los archivos locales.

**`triage_redis.py`**
Gestiona la cola de espera y los 5 boxes en Redis. Calcula la prioridad de cada paciente como `timestamp_llegada + tiempo_max_espera_min * 60`: cuanto menor es el score, antes debe atenderse. Usa una lista ordenada (`ZADD` / `ZPOPMIN`) para sacar siempre al más urgente y hashes `box:1`…`box:5` para saber quién ocupa cada box. Al dar un alta, libera el box y mete al siguiente de la cola. `initialize_boxes()` comprueba la conexión y prepara los boxes.

**`consultas.py`**
Contiene las dos consultas analíticas del reto. `consulta_1()` calcula la estancia media por categoría patológica con un pipeline de agregación (`$match`, `$project`, `$group`, `$sort`). `consulta_2()` agrupa por tramos de edad con `$bucket` y calcula el porcentaje de domicilio frente a ingreso en planta. `mostrar_consultas()` las imprime con formato para la opción 3 del menú.

**`analytics_mongo.py`**
Solo reexporta `consulta_1`, `consulta_2` y `mostrar_consultas` desde `consultas.py`. Antes borraba la colección al importarse; ahora no toca la base de datos. Se puede ejecutar con `python -m src.analytics_mongo` para ver las consultas sin abrir el menú.

**`anonymizer.py`**
Reservado para la parte opcional de anonimización/RGPD. Actualmente está vacío y no se usa en el flujo.

**`main.py`** (raíz del proyecto)
Es el punto de entrada. Muestra el menú y llama al ETL (1), a la migración (2), a las consultas (3) y arranca el worker en un hilo aparte (4). Captura los errores de cada opción para que el menú no se cierre, y al salir detiene el worker y cierra las conexiones de Mongo y Redis.

---

## 5. Notas

- La colección que se usa es `hospital_db.episodios_urgencias`.
- `data/migracion_mongo.json` no se sube a Git: se regenera con la opción 1 o 2.
- El worker consulta la API cada 5 segundos.
