# -*- coding: utf-8 -*-
# Copyright (C) 2023 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

# Carga NVDA
import addonHandler
import config
import globalVars
# Carga estándar
import os
import shutil
from collections import deque

# Carga traducción
addonHandler.initTranslation()

def recursive_overwrite(src, dest, ignore=None):
	"""
    Sobreescribe de manera recursiva los archivos de un directorio origen (src) a un directorio destino (dest).

    Parámetros:
    src (str): La ruta del directorio o archivo origen.
    dest (str): La ruta del directorio o archivo destino.
    ignore (callable, opcional): Una función callable que toma dos argumentos (src, archivos) y retorna un conjunto de nombres de archivos a ignorar.

    Returns:
    None

    Ejemplos:
    >>> recursive_overwrite('/ruta/del/directorio/origen', '/ruta/del/directorio/destino')
    >>> recursive_overwrite('/ruta/del/archivo/origen', '/ruta/del/archivo/destino', ignore=lambda src, files: {'archivo_a_ignorar.txt'})
    
    Notas:
    - Si `src` es un directorio, la función se llama a sí misma de manera recursiva para cada archivo o subdirectorio en `src`.
    - Si `src` es un archivo, simplemente se copia en `dest`.
    - Si `dest` no existe, se creará.
    - La función `ignore` se utiliza para ignorar ciertos archivos durante la copia. Debe retornar un conjunto de nombres de archivos para ignorar.
	"""
	if os.path.isdir(src):
		if not os.path.isdir(dest):
			os.makedirs(dest)
		files = os.listdir(src)
		if ignore is not None:
			ignored = ignore(src, files)
		else:
			ignored = set()
		for f in files:
			if f not in ignored:
				recursive_overwrite(os.path.join(src, f), os.path.join(dest, f), ignore)
	else:
		shutil.copyfile(src, dest)

### Variables directorio y ficheros
dir_root = os.path.join(addonHandler.getCodeAddon().path, "globalPlugins", "TranslateOffline")
dir_data = os.path.join(dir_root, "data")
dir_srv = os.path.join(dir_root, "server")
dir_models = os.path.join(dir_root, "server", "models")
dir_root_config = globalVars.appArgs.configPath
dir_root_config_temp = os.path.join(dir_root_config, "TranslateOfflineTemp")
dir_cache = os.path.join(dir_root_config, "TranslateOfflineCache")
if not os.path.isdir(dir_data): # Si no existe creamos directorio
	os.makedirs(dir_data)
if not os.path.isdir(dir_cache): # Si no existe creamos directorio
	os.makedirs(dir_cache)

file_json_filter = os.path.join(dir_data, "languages_srv.json")
file_json_languages = os.path.join(dir_data, "languages.json")

### Comprueba si hay temporales
if os.path.isdir(dir_root_config_temp):
	for filename in os.listdir(dir_models):
		file_path = os.path.join(dir_models, filename)
		try:
			if os.path.isfile(file_path) or os.path.islink(file_path):
				os.unlink(file_path)
			elif os.path.isdir(file_path):
				shutil.rmtree(file_path)
		except Exception as e:
			pass
	recursive_overwrite(dir_root_config_temp, dir_models)
	try:
		shutil.rmtree(dir_root_config_temp, ignore_errors=True)
	except:
		pass

### Historial
historialOrigen = deque(maxlen=500)
historialDestino = deque(maxlen=500)

### Banderas de control
IS_WinON = False
IS_Cliente = False
IS_Reinicio = False
IS_Sonido = False
is_active_translate = False

### Variables para conexión del cliente con servidor
idMaquina = None
puerto = None
cliente = None
procesamiento = "cpu"

### Variables del traductor
_translationCache = {}
_nvdaSpeak = None
_nvdaGetPropertiesSpeech = None
_enableTranslation = False
_enableTranslationOnline = False
_lastTranslatedText = None
indiceLangOrigen = 0
indiceLangDestino = 0

### Configuración nvda.ini
def initConfiguration():
	confspec = {
		"langOrigen": "string(default='0')",
		"langDestino": "string(default='0')",
		"autodetect": "boolean(default=False)",
		"cache": "boolean(default=False)",
	}
	config.conf.spec['TranslateOffline'] = confspec

def getConfig(key):
	return config.conf["TranslateOffline"][key]

def setConfig(key, value):
	try:
		config.conf.profiles[0]["TranslateOffline"][key] = value
	except:
		config.conf["TranslateOffline"][key] = value

choiceLangOrigen = None
choiceLangDestino = None
chkAutoDetect = None
chkCache = None
chkTextLargo = False

def setup():
	global choiceLangOrigen, choiceLangDestino, chkAutoDetect, chkCache
	initConfiguration()
	choiceLangOrigen = getConfig("langOrigen")
	choiceLangDestino = getConfig("langDestino")
	chkAutoDetect = getConfig("autodetect")
	chkCache = getConfig("cache")

def guardaConfiguracion():
	setConfig("langOrigen", choiceLangOrigen)
	setConfig("langDestino", choiceLangDestino)
	setConfig("autodetect", chkAutoDetect)
	setConfig("cache", chkCache)
