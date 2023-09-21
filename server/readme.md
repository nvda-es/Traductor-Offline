# Servidor para el Traductor Offline

Empezare esta documentación advirtiendo que no soy bueno haciendo servidores y manejando dicho tema.

Por lo que el servidor es algo sencillo y funcional con posibilidad de ser mejorado con los conocimientos adecuados.

Después de leer mucho e investigar me decline por hacerlo en multiprocessing por que según mi entender es más rápido y maneja mejor el cambio de información.

El servidor esta abierto a aportaciones para mejorarlo.

No voy a extenderme mucho en su explicación ya que no es el cometido, simplemente dejo el código fuente para que pueda ser comprobado que no contiene nada raro y que cualquiera puede generar el servidor y añadirlo al complemento para NVDA.

Se comparte el código fuente también para que si alguien tiene mayores conocimientos pueda aportar y por temas de confiabilidad ya que es peligroso aceptar complementos que contengan ejecutables y que no podamos saber realmente que hacen.

En este caso se adjunta el código fuente para que pueda ser revisado y comprobar que el único cometido es comunicar las librerías necesarias que solo pueden ejecutarse en 64 bits y al no ser admitidas por NVDA es necesario crear un ejecutable.

El servidor a sido creado en Python 3.11 de 64 Bits y es el que aconsejo por ser más rápido que otras versiones inferiores.

## Explicación de carpetas y ficheros

* Carpetas auto, logs y models.

Dentro esta el correspondiente readme con una breve explicación.

* gestor_logs.py y TranslateOfflineSRV.py

Estos dos archivos es el código fuente del servidor.

* nuevo_entorno.bat, requerimientos.txt, requerimientos_install.bat, setup.py y start.bat

Estos archivos son para crear un entorno virtual de Python 3.11, los requisitos a instalar por pip del servidor, el archivo setup.py para crear el ejecutable y un archivo para facilitar la creación desde el entorno virtual rápidamente el ejecutable.

## Creación del ejecutable

Voy a explicar sencillamente como creo yo el ejecutable.

Lo primero e indispensable es tener instalado Python 3.11 de 64 Bits.

Una vez tenemos instalado Python yo aconsejo usar el archivo nuevo_entorno.bat para que se genere automáticamente en el mismo directorio un directorio llamado 3.11.

En este directorio tendremos un entorno virtual para poder añadir las librerías necesarias y así no ensuciar nuestro Python instalado.

Comentar sobre el archivo nuevo_entorno.bat que esta preparado por si tenemos instalado 2 Python por ejemplo de 32 y 64, se usa PyLauncher para decirle que trabaje con Python 3.11, este archivo en caso de no tener instalado PyLauncher tendremos que modificarlo.

Segundo tendremos que instalar las librerías necesarias, e puesto el archivo requerimientos_install.bat que lo que hace es ejecutar nuestro entorno virtual y instalar el contenido del archivo requerimientos.txt a través de pip.

Este paso podemos hacerlo también manualmente ejecutando nuestro entorno virtual y instalando el archivo requerimientos.txt con pip.

Pip install -r requerimientos.txt

Tercero ya solo queda generar el servidor, para ello e incluido el archivo start.bat que lo que hace es ejecutar nuestro entorno virtual y decirle a Python que ejecute el archivo setup.py para que cx_Freeze genere un directorio llamado server y dentro ponga el ejecutable con todo lo necesario para ejecutar el servidor.

Este paso también podemos hacerlo manualmente ejecutando nuestro entorno virtual y lanzar el setup.py

Python setup.py build

# Carpeta resultante server

La carpeta resultante llamada server que se crea después de generar el ejecutable tenemos que copiarla al directorio:

Addon/ globalPlugins/ TranslateOffline

Esto tenemos que hacerlo antes de generar el complemento para que se añada la carpeta del servidor necesario para el uso del complemento.
