# Pipelines de agregación analítica.
#
# Las dos consultas del reto viven en src/consultas.py para poder mostrarlas
# también desde el menú de main.py sin duplicar código.
# Antes este archivo borraba la colección e insertaba el JSON al importarse,
# así que ahora solo expone las consultas y no toca la base de datos.

from .consultas import consulta_1, consulta_2, mostrar_consultas

if __name__ == "__main__":
    mostrar_consultas()
