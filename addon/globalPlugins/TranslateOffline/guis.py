# -*- coding: utf-8 -*-
# Copyright (C) 2023 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

# Carga NVDA
import addonHandler
import logHandler
import languageHandler
import globalVars
import gui
import ui
from gui.nvdaControls import CustomCheckListBox
# Carga estándar
import os
import sys
import wx
import wx.adv
import json
import re
import shutil
import uuid
import socket
import time
import ctypes
from ctypes import wintypes
from ctypes.wintypes import HWND, UINT, LPCWSTR, BOOL
from urllib import request, error
from random import choice
from threading import Thread, Event
# Carga personal
from .lib import psutil
from . import settings

# Carga traducción
addonHandler.initTranslation()

	# Definición manual de tipos de datos necesarios
## Pertenece a eliminar proceso
DWORD = ctypes.c_ulong
LONG = ctypes.c_long
ULONG_PTR = ctypes.POINTER(DWORD)
MAX_PATH = 260
## Pertenece a eliminar directorio
SHFileOperationW = ctypes.windll.shell32.SHFileOperationW
FO_DELETE = 0x3
FOF_SILENT = 0x4
FOF_NOCONFIRMATION = 0x10

class Clipboard:
	def __init__(self):
		"""
		Inicializa la clase Clipboard con las constantes y funciones necesarias
		para interactuar con el portapapeles de Windows a través de ctypes.
		"""
		self.CF_UNICODETEXT = 13
		self.GMEM_MOVEABLE = 0x0002
		self.GMEM_ZEROINIT = 0x0040
		self.unicode_type = type(u'')

		self.OpenClipboard = ctypes.windll.user32.OpenClipboard
		self.OpenClipboard.argtypes = ctypes.POINTER(ctypes.c_int),
		self.OpenClipboard.restype = ctypes.c_int
		self.EmptyClipboard = ctypes.windll.user32.EmptyClipboard
		self.EmptyClipboard.restype = ctypes.c_int
		self.GetClipboardData = ctypes.windll.user32.GetClipboardData
		self.GetClipboardData.argtypes = ctypes.c_uint,
		self.GetClipboardData.restype = ctypes.c_void_p
		self.SetClipboardData = ctypes.windll.user32.SetClipboardData
		self.SetClipboardData.argtypes = ctypes.c_uint, ctypes.c_void_p
		self.SetClipboardData.restype = ctypes.c_void_p
		self.CloseClipboard = ctypes.windll.user32.CloseClipboard
		self.CloseClipboard.restype = ctypes.c_int

		self.GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
		self.GlobalAlloc.argtypes = ctypes.c_uint, ctypes.c_size_t
		self.GlobalAlloc.restype = ctypes.c_void_p
		self.GlobalLock = ctypes.windll.kernel32.GlobalLock
		self.GlobalLock.argtypes = ctypes.c_void_p,
		self.GlobalLock.restype = ctypes.c_void_p
		self.GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
		self.GlobalUnlock.argtypes = ctypes.c_void_p,
		self.GlobalSize = ctypes.windll.kernel32.GlobalSize
		self.GlobalSize.argtypes = ctypes.c_void_p,
		self.GlobalSize.restype = ctypes.c_size_t

	def clean(self):
		"""
		Limpia el contenido del portapapeles. Si no puede abrir el portapapeles,
		lanza una excepción RuntimeError.
		"""
		if self.OpenClipboard(None):
			self.EmptyClipboard()
			self.CloseClipboard()
		else:
			raise RuntimeError("No se pudo abrir el portapapeles")

	def get(self):
		"""
		Obtiene el texto del portapapeles. Retorna el texto como una cadena unicode.
		"""
		text = None
		self.OpenClipboard(None)
		handle = self.GetClipboardData(self.CF_UNICODETEXT)
		pcontents = self.GlobalLock(handle)
		size = self.GlobalSize(handle)
		if pcontents and size:
			raw_data = ctypes.create_string_buffer(size)
			ctypes.memmove(raw_data, pcontents, size)
			text = raw_data.raw.decode('utf-16le').rstrip(u'\0')
		self.GlobalUnlock(handle)
		self.CloseClipboard()
		return text

	def put(self, text):
		"""
		Establece el texto en el portapapeles. El texto debe ser una cadena unicode.
		"""
		if not isinstance(text, self.unicode_type):
			text = text.decode('mbcs')
		data = text.encode('utf-16le')
		self.OpenClipboard(None)
		self.EmptyClipboard()
		handle = self.GlobalAlloc(self.GMEM_MOVEABLE | self.GMEM_ZEROINIT, len(data) + 2)
		pcontents = self.GlobalLock(handle)
		ctypes.memmove(pcontents, data, len(data))
		self.GlobalUnlock(handle)
		self.SetClipboardData(self.CF_UNICODETEXT, handle)
		self.CloseClipboard()

class utilidades:
	"""
		Esta clase contendrá diversas utilidades
	"""
	class SHFILEOPSTRUCTW(ctypes.Structure):
		"""Pertenece a borrar directorio"""
		_fields_ = [
			('hwnd', HWND),
			('wFunc', UINT),
			('pFrom', LPCWSTR),
			('pTo', LPCWSTR),
			('fFlags', UINT),
			('fAnyOperationsAborted', BOOL),
			('hNameMappings', HWND),
			('lpszProgressTitle', LPCWSTR),
		]

	class PROCESSENTRY32(ctypes.Structure):
		""" Pertenece a eliminar proceso"""
		_fields_ = [
			("dwSize", DWORD),
			("cntUsage", DWORD),
			("th32ProcessID", DWORD),
			("th32DefaultHeapID", ULONG_PTR),
			("th32ModuleID", DWORD),
			("cntThreads", DWORD),
			("th32ParentProcessID", DWORD),
			("pcPriClassBase", LONG),
			("dwFlags", DWORD),
			("szExeFile", ctypes.c_char * MAX_PATH)
		]

	@staticmethod
	def kill_process_by_name(proceso):
		"""
        Termina un proceso por su nombre utilizando ctypes y kernel32.
		"""
		PROCESS_TERMINATE = 1
		handle = ctypes.windll.kernel32.CreateToolhelp32Snapshot(ctypes.c_uint32(0x2), ctypes.c_uint32(0))
		entry = ProcessUtils.PROCESSENTRY32()
		entry.dwSize = ctypes.sizeof(entry)

		found_process = False
		while ctypes.windll.kernel32.Process32Next(handle, ctypes.byref(entry)):
			try:
				if proceso.lower() == entry.szExeFile.decode('utf-8').lower():
					handle_process = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, entry.th32ProcessID)
					ctypes.windll.kernel32.TerminateProcess(handle_process, 0)
					ctypes.windll.kernel32.CloseHandle(handle_process)
				found_process = True
			except:
				try:
					if proceso.lower() == entry.szExeFile.decode('latin-1').lower():
						handle_process = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, entry.th32ProcessID)
						ctypes.windll.kernel32.TerminateProcess(handle_process, 0)
						ctypes.windll.kernel32.CloseHandle(handle_process)
					found_process = True
				except:
					try:
						if proceso.lower() == entry.szExeFile.decode('cp1252').lower():
							handle_process = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, entry.th32ProcessID)
							ctypes.windll.kernel32.TerminateProcess(handle_process, 0)
							ctypes.windll.kernel32.CloseHandle(handle_process)
						found_process = True
					except:
						found_process = False
		return found_process

	def verificar_instalacion(lista):
		"""
		Esta función verifica si hay suficiente espacio en el disco duro 
		para instalar todos los elementos de la lista proporcionada. 
		Cada elemento en la lista se asume que ocupa 400 MB.

		Parámetros:
		lista (list): Una lista de elementos a instalar.

		Retorno:
		bool: True o False indicando si hay suficiente espacio para la instalación.
		"""

		# Paso 1: Contar elementos en la lista
		numero_de_elementos = len(lista)
		
		# Paso 2: Calcular espacio necesario para la instalación (en megabytes)
		espacio_necesario_mb = numero_de_elementos * 400  # 400 MB por elemento
		
		# Paso 3: Verificar espacio disponible en el disco duro
		ruta_programa = os.path.abspath(addonHandler.getCodeAddon().path)
		disco = psutil.disk_usage(ruta_programa)
		
		# Convertir el espacio disponible a megabytes
		espacio_disponible_mb = disco.free / (1024 * 1024)
		
		# Verificar si hay espacio suficiente para la instalación
		if espacio_necesario_mb <= espacio_disponible_mb:
			return True
		else:
			return False

	def is_connected():
		"""Comprueba si hay conexión a internet utilizando ctypes"""
		INTERNET_CONNECTION_OFFLINE = 0x20
		INTERNET_CONNECTION_CONFIGURED = 0x40
		INTERNET_CONNECTION_LAN = 0x02
		INTERNET_CONNECTION_MODEM = 0x01
		INTERNET_CONNECTION_PROXY = 0x04
		INTERNET_RAS_INSTALLED = 0x10
		INTERNET_CONNECTION_MODEM_BUSY = 0x08
		INTERNET_CONNECTION_ONLINE = 0x01

		# Cargar la biblioteca wininet.dll
		wininet = ctypes.WinDLL("wininet.dll")

		# Comprobar el estado de conexión
		flags = ctypes.c_int(0)
		connection = wininet.InternetGetConnectedState(ctypes.byref(flags), 0)

		# Analizar los indicadores de conexión
		if connection:
			return not bool(flags.value & INTERNET_CONNECTION_OFFLINE)
		else:
			return False

	def id_maquina():
		"""
    Genera y retorna una cadena única que representa la ID de la máquina.

    La ID de la máquina es una cadena que se forma a partir de una parte 
    del UUID generado con la dirección MAC de la máquina y un timestamp.

    Returns:
        str: Una cadena que representa la ID única de la máquina.
		"""
		return str(uuid.uuid1(uuid.getnode(),0))[24:]

	def procesoCHK(proceso):
		"""
    Verifica si un proceso está actualmente en ejecución en la máquina.

    Args:
        proceso (str): El nombre del proceso a verificar.

    Returns:
        bool: True si el proceso está en ejecución, False en caso contrario.
		"""
		return proceso in (p.name() for p in psutil.process_iter())

	def puertoUsado(puerto: int) -> bool:
		"""
    Verifica si un puerto específico está siendo utilizado en la máquina local.

    Args:
        puerto (int): El número de puerto a verificar.

    Returns:
        bool: True si el puerto está siendo utilizado, False en caso contrario.
		"""
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			return s.connect_ex(('localhost', puerto)) == 0

	def obtenPuerto():
		"""
    Obtiene un número de puerto disponible en el rango de 49152 a 65535.

    El método consiste en seleccionar aleatoriamente un puerto dentro del rango 
    especificado y verificar si está siendo utilizado. Si está siendo utilizado, 
    selecciona otro puerto aleatoriamente hasta que encuentra uno disponible.

    Returns:
        int: Un número de puerto disponible.
		"""
		bandera = True
		while bandera:
			puerto = choice([i for i in range(49152, 65535) if i not in []])
			if utilidades.puertoUsado(puerto):
				pass
			else:
				bandera = False
		return puerto

	def limpiaLista(lista):
		resultado = []
		for i in lista:
			try:
				x = i.lstrip().rstrip()
			except:
				x = i
			if x == "Traducción activada.":
				pass
			elif x == "en blanco":
				pass
			else:
				resultado.append(x)
		return resultado

class HelsinkiNLPModelFilter:
	"""
	Esta clase permite filtrar modelos específicos desde un archivo JSON que contiene detalles 
	sobre varios modelos de Helsinki-NLP.
	"""

	def __init__(self, output_filepath):
		"""
		Inicializa la clase con la ruta donde se guardará el archivo JSON de salida.
		
		:param output_filepath: La ruta del archivo JSON donde se guardarán los datos filtrados.
		"""

		self.output_filepath = output_filepath

	def fetch_data(self):
		"""
		Recupera los datos de los modelos desde la API de Hugging Face.
		"""
		try:
			url = "https://huggingface.co/api/models?library=Helsinki-NLP"
			response = request.urlopen(url)
			data = json.loads(response.read())
			return data
		except Exception as e:
			logHandler.log.error_((f"Ocurrió un error al obtener los datos de Hugging Face: {e}"))
			return []

	def filter_models(self):
		"""
		Filtra los modelos basándose en varios criterios y guarda los modelos filtrados en un archivo JSON.
		"""
		try:
			data = self.fetch_data()

			# Filtramos los bloques que contienen "modelId" que incluyen la cadena "Helsinki-NLP/opus-mt-" y terminan con el patrón "xx-xx"
			filtered_data = []
			for item in data:
				match = re.fullmatch(r'.*-([a-z]{2})-([a-z]{2})', item['modelId'])
				if 'Helsinki-NLP/opus-mt-' in item['modelId'] and match:
					item['source_language'] = match.group(1)
					item['target_language'] = match.group(2)
					if 'text2text-generation' in item['tags'] and 'translation' in item['tags'] and item.get('pipeline_tag') == 'translation':
						filtered_data.append(item)

			# Guardamos los bloques filtrados en un nuevo archivo JSON
			with open(self.output_filepath, 'w') as f:
				json.dump(filtered_data, f, indent="\t")
			return True
		except Exception as e:
			logHandler.log.error(_(f"Ocurrió un error durante el filtrado de modelos: {e}"))
			return False

class HelsinkiNLPModelData:
	"""
	Esta clase permite obtener diversos tipos de datos de un archivo JSON que contiene información 
	sobre varios modelos de Helsinki-NLP filtrados previamente.

	 También carga el fichero de lenguaje con los códigos y países y define diversas utilidades.
	"""
	def __init__(self, input_filepath, input_filepath_languages):
		"""
		Inicializa la clase con la ruta del archivo JSON de entrada.
		
		:param input_filepath: La ruta del archivo JSON de donde se leerán los datos que tienen todas las referencias de los idiomas.  .
		:param input_filepath_languages: La ruta del archivo JSON de donde se leerán  los idiomas en nombre completo.
		"""

		self.input_filepath = input_filepath
		self.input_filepath_languages = input_filepath_languages
		self.data = []
		self.data_lang = {}

	def load_data(self):
		"""
		Carga los datos de los archivos JSON en una variable de instancia.
		"""
		try:
			with open(self.input_filepath, 'r', encoding='utf-8') as f:
				self.data = json.load(f)
			with open(self.input_filepath_languages, 'r', encoding='utf-8') as f:
				self.data_lang = json.load(f)
			return True
		except Exception as e:
			logHandler.log.error(_(f"Ocurrió un error al cargar los datos: {e}"))
			self.data = []
			self.data_lang = {}
			return False

	def get_languages(self):
		"""
		Obtiene y muestra una lista de todos los pares de idiomas (origen y destino) presentes en el archivo JSON.
		"""
		try:
			languages = [(item['source_language'], item['target_language']) for item in self.data]
			return languages
		except Exception as e:
			logHandler.log.error(_(f"Ocurrió un error al obtener los idiomas: {e}"))
			return []

	def get_language_names(self, reference_language_code, language_codes):
		"""
    Esta función toma un código de idioma de referencia y una lista de códigos de idiomas, 
    y devuelve una lista de nombres de idiomas en el idioma de referencia.
    
    :param reference_language_code: El código de idioma de referencia (por ejemplo, 'es' para español)
    :param language_codes: Una lista de códigos de idiomas (por ejemplo, ['en', 'fr'])
    
    :return: Una lista de nombres de idiomas en el idioma de referencia
		"""
		reference_language_dict = self.data_lang.get(reference_language_code, {})
		return [reference_language_dict.get(code, "Unknown") for code in language_codes]

	def get_language_codes(self, reference_language_code, language_names):
		"""
    Esta función toma un código de idioma de referencia y una lista de nombres de idiomas en ese idioma de referencia,
    y devuelve una lista de códigos de idiomas correspondientes.
    
    :param reference_language_code: El código de idioma de referencia (por ejemplo, 'es' para español)
    :param language_names: Una lista de nombres de idiomas en el idioma de referencia (por ejemplo, ['Inglés', 'Francés'])
    
    :return: Una lista de códigos de idiomas correspondientes
		"""
		reference_language_dict = self.data_lang.get(reference_language_code, {})
		reverse_dict = {v: k for k, v in reference_language_dict.items()}
		return [reverse_dict.get(name, "Unknown") for name in language_names]

	def get_model_id_by_index(self, index):
		"""
    Esta función toma un índice y devuelve el model_id correspondiente en ese índice.
    
    :param index: Índice del modelo en la lista
    
    :return: El model_id en el índice dado o None si el índice no es válido
		"""
		try:
			return self.data[index]['modelId']
		except IndexError:
			return None

	def get_model_id_code(self, language_pair):
		"""
		Esta función toma una pareja de códigos de idiomas y devuelve el modelId correspondiente.

		Args:
		language_pair (list): Una lista con dos códigos de idiomas (por ejemplo, ["es", "en"]).

		Returns:
		str: El modelId correspondiente, o None si no se encuentra una coincidencia.
		"""
		for entry in self.data:
			if entry['source_language'] == language_pair[0] and entry['target_language'] == language_pair[1]:
				return entry['modelId']
		return None

	def get_languages_installed(self):
		"""
            Función para obtener en una lista los códigos de los lenguajes instalados
		"""
		language_codes = []
		for model_name in os.listdir(settings.dir_models):
			model_path = os.path.join(settings.dir_models, model_name)
			if os.path.isdir(model_path):
				language_codes.append(model_name.split('-')[-2:])
		return language_codes

##### Inicio parte interface dialogo gestor de idiomas
class LanguageDialog(wx.Dialog):
	def __init__(self, parent, frame):
		super(LanguageDialog, self).__init__(parent, -1)

		settings.IS_WinON = True
		self.SetSize((800, 600))
		self.SetTitle(_("Gestor de idiomas"))
		self.frame = frame
		self.datos = self.frame.HelsinkiNLPModelData
		if not self.datos.load_data():
			logHandler.log.error(_("Error al cargar los JSON desde el gestor de idiomas."))
			settings.IS_WinON = False
			self.Destroy()
			gui.mainFrame.postPopup()
			return

		self.datos_lang_nombre = []
		self.datos_lang_nombre_installed = []

		self.bloqueo = False
		self.panel = wx.Panel(self)
		self.notebook = wx.Notebook(self.panel)
		
		# Pestaña de idiomas disponibles
		self.available_page = wx.Panel(self.notebook)
		label_1 = wx.StaticText(self.available_page, wx.ID_ANY, _("Idiomas &Disponibles:"))
		self.available_listbox = CustomCheckListBox(self.available_page, 100)
		self.install_button = wx.Button(self.available_page, label=_("&Instalar"))
		available_sizer = wx.BoxSizer(wx.VERTICAL)
		available_sizer.Add(label_1, 0, wx.EXPAND, 5)
		available_sizer.Add(self.available_listbox, 1, wx.EXPAND | wx.ALL, 5)
		available_sizer.Add(self.install_button, 0, wx.ALL, 5)
		self.available_page.SetSizer(available_sizer)
		
		# Pestaña de idiomas instalados
		self.installed_page = wx.Panel(self.notebook)
		label_2 = wx.StaticText(self.installed_page, wx.ID_ANY, _("Idiomas &Instalados:"))
		self.installed_listbox = CustomCheckListBox(self.installed_page, 200, choices=[])
		self.uninstall_button = wx.Button(self.installed_page, label=_("&Desinstalar"))
		installed_sizer = wx.BoxSizer(wx.VERTICAL)
		installed_sizer.Add(label_2, 0, wx.EXPAND, 5)
		installed_sizer.Add(self.installed_listbox, 1, wx.EXPAND | wx.ALL, 5)
		installed_sizer.Add(self.uninstall_button, 0, wx.ALL, 5)
		self.installed_page.SetSizer(installed_sizer)
		
		# Añadir páginas al cuaderno
		self.notebook.AddPage(self.available_page, "Idiomas Disponibles")
		self.notebook.AddPage(self.installed_page, "Idiomas Instalados")
		
		# Botones de actualizar y cerrar
		self.update_button = wx.Button(self.panel, label=_("&Actualizar Idiomas Disponibles"))
		self.close_button = wx.Button(self.panel, label=_("&Cerrar"))
		
		# Organizar el layout
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.notebook, 1, wx.EXPAND)
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		button_sizer.Add(self.update_button, 1, wx.ALL, 5)
		button_sizer.Add(self.close_button, 1, wx.ALL, 5)
		sizer.Add(button_sizer, 0, wx.EXPAND)
		
		self.panel.SetSizer(sizer)
		
		self.CenterOnScreen()
		
		self.on_events()
		self.inicio()

	def on_events(self):
		# Eventos
		self.install_button.Bind(wx.EVT_BUTTON, self.on_install)
		self.uninstall_button.Bind(wx.EVT_BUTTON, self.on_uninstall)
		self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
		self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
		self.Bind(wx.EVT_CLOSE, self.on_close)
		self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyEvent)

	def inicio(self):
		self.datos_lang_nombre = []
		self.datos_lang_nombre_installed = []
		self.datos_lang_nombre = [self.datos.get_language_names("es" if languageHandler.getLanguage()[:2] == "es" else "en", i) for i in self.datos.get_languages()]
		self.datos_lang_nombre_installed = [self.datos.get_language_names("es" if languageHandler.getLanguage()[:2] == "es" else "en", i) for i in self.datos.get_languages_installed()]

		self.available_listbox.Clear()
		self.available_listbox.Append([f"{i[0]} - {i[1]}" for i in self.datos_lang_nombre])
		self.available_listbox.SetSelection(0)
		self.available_listbox.SetFocus()
		self.installed_listbox.Clear()
		if len(self.datos_lang_nombre_installed):
			self.installed_listbox.Append([f"{i[0]} - {i[1]}" for i in self.datos_lang_nombre_installed])
			self.installed_listbox.SetSelection(0)
			self.uninstall_button.Enable()
		else:
			self.installed_listbox.Append(_("Sin idiomas instalados"))
			self.installed_listbox.SetSelection(0)
			self.uninstall_button.Disable()
			settings.choiceLangOrigen = "0"
			settings.choiceLangDestino = "0"
			settings.setConfig("langOrigen",settings.choiceLangOrigen)
			settings.setConfig("langDestino",settings.choiceLangDestino)

	def on_install(self, event):
		if not utilidades.is_connected():
			msg= \
_("""No se a encontrado conexión a internet.

Compruebe que todo esta correcto.""")
			gui.messageBox(msg, _("Error"), wx.OK| wx.ICON_ERROR)
			self.available_listbox.SetFocus()
			return

		selections = [i for i in range(self.available_listbox.GetCount()) if self.available_listbox.IsChecked(i)]
		if not len(selections):
			gui.messageBox(_("Necesita elegir al menos un idioma para continuar."), _("Error"), wx.OK| wx.ICON_ERROR)
			self.available_listbox.SetFocus()
			return

		if utilidades.verificar_instalacion(selections) is False:
			msg = \
_("""No hay espacio suficiente para la instalación.

Cada paquete de idiomas son aproximadamente 350 MB.""")
			gui.messageBox(msg, _("Error"), wx.OK| wx.ICON_ERROR)
			self.available_listbox.SetFocus()
			return

		items_seleccionados = [self.available_listbox.GetString(i) for i in range(self.available_listbox.GetCount()) if self.available_listbox.IsChecked(i)]
		items_instalados = [self.installed_listbox.GetString(i) for i in range(self.installed_listbox.GetCount())]

		if items_seleccionados == items_instalados:
			msg = \
_("""Los paquetes de idioma que a elegido ya se encuentran instalados.

¿Desea actualizar dichos paquetes?""")
			dialog = wx.MessageDialog(None, msg, _('Confirmar'), wx.YES_NO | wx.ICON_QUESTION)
			result = dialog.ShowModal()
			if result == wx.ID_YES:
				dialog.Destroy()
				paquetes =[self.datos.get_model_id_by_index(i) for i in selections]
				idiomas = items_seleccionados
			else:
				dialog.Destroy()
				return
		elif len(items_seleccionados) == 1 and items_seleccionados[0] in items_instalados and len(items_instalados) > 1:
			msg = \
_("""El paquete de idioma que ha seleccionado ya esta instalado.

¿Desea actualizarlo?""")
			dialog = wx.MessageDialog(None, msg, _('Confirmar'), wx.YES_NO | wx.ICON_QUESTION)
			result = dialog.ShowModal()
			if result == wx.ID_YES:
				dialog.Destroy()
				paquetes =[self.datos.get_model_id_by_index(i) for i in selections]
				idiomas = items_seleccionados
			else:
				dialog.Destroy()
				return
		elif any(item in items_instalados for item in items_seleccionados):
			msg = \
_("""En la selección que a echo hay paquetes que ya están instalados.

Presione SI para actualizar los instalados y instalar los nuevos.

Presione NO para instalar solo los paquetes nuevos.""")
			dialog = wx.MessageDialog(None, msg, _('Confirmar'), wx.YES_NO | wx.ICON_QUESTION)
			result = dialog.ShowModal()
			if result == wx.ID_YES:
				dialog.Destroy()
				paquetes =[self.datos.get_model_id_by_index(i) for i in selections]
				idiomas = items_seleccionados
			else:
				dialog.Destroy()
				idiomas = []
				indices_no_instalados = []
				for i in selections:
					item = self.available_listbox.GetString(i)
					if item not in items_instalados:
						idiomas.append(item)
						indices_no_instalados.append(i)
				paquetes = [self.datos.get_model_id_by_index(i) for i in indices_no_instalados]
		else:
			paquetes =[self.datos.get_model_id_by_index(i) for i in selections]
			idiomas = items_seleccionados

		dlg = DescargaDialogo(settings.dir_models, paquetes, idiomas)
		result = dlg.ShowModal()
		if result == 0: # Correcto
			dlg.Destroy()
			self.frame.onReboot(None)
			self.inicio()
		elif result == 1: # correcto algunos idiomas instalados
			dlg.Destroy()
			self.frame.onReboot(None)
			self.inicio()
		elif result == 2: # Nincun idioma instalado.
			dlg.Destroy()
			self.available_listbox.SetFocus()

	def on_uninstall(self, event):
		selections = [i for i in range(self.installed_listbox.GetCount()) if self.installed_listbox.IsChecked(i)]
		if not len(selections):
			gui.messageBox(_("Necesita elegir al menos un idioma para continuar."), _("Error"), wx.OK| wx.ICON_ERROR)
			self.installed_listbox.SetFocus()
			return
		items_seleccionados = [self.installed_listbox.GetString(i) for i in range(self.installed_listbox.GetCount()) if self.installed_listbox.IsChecked(i)]

		if len(selections) == 1:
			msg = \
_("""El paquete de idioma que ha seleccionado se eliminara.

Este proceso no se puede deshacer.

¿Desea continuar?""")
		elif len(selections) > 1:
			msg = \
_("""Los paquetes de idioma que ha seleccionado se eliminaran.

Este proceso no se puede deshacer.

¿Desea continuar?""")
		dialog = wx.MessageDialog(None, msg, _('Confirmación'), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
		result = dialog.ShowModal()
		if result == wx.ID_YES:
			dialog.Destroy()
			self.on_delete_model(selections)
			self.frame.onReboot(None)
			self.inicio()
			self.installed_listbox.SetFocus()
			self.bloqueo = False
		else:
			dialog.Destroy()
		

	def on_delete_model(self, selections):
		self.bloqueo = True
		error_item = []
		errors = []
		for i in selections:
			item = self.installed_listbox.GetString(i)
			code = self.datos.get_language_codes("es" if languageHandler.getLanguage()[:2] == "es" else "en", self.datos_lang_nombre_installed[i])
			modelo = self.datos.get_model_id_code(code)
			modelo_actual_path = os.path.join(settings.dir_models, modelo.split('/')[-1])
			try:
				shutil.rmtree(modelo_actual_path)
			except Exception as e:
				error_item.append(item)
				errors.append(e)

		if len(errors) == len(selections):
			msg = \
_("""No se a podido borrar ningún paquete de idioma seleccionado.

Paquete de idioma / error:

{}""").format("\n\n".join(f"{item}\n{error}" for item, error in zip(error_item, errors)))
			gui.messageBox(msg, _("Error"), wx.OK| wx.ICON_ERROR)
		elif len(errors) > 0:
			msg = \
_("""Se a producido algún error en alguno de los paquetes de idiomas seleccionado.

Paquete de idioma / error:

{}

El servidor de traducción se reiniciará cuando acepte.""").format("\n\n".join(f"{item}\n{error}" for item, error in zip(error_item, errors)))
			gui.messageBox(msg, _("Información"), wx.OK| wx.ICON_INFORMATION)
		else:
			msg = \
_("""Todos los paquetes de idioma seleccionados fueron borrados.

El servidor de traducción se reiniciará cuando acepte.""")
			gui.messageBox(msg, _("Información"), wx.OK| wx.ICON_INFORMATION)

	def on_update(self, event):
		Thread(target=self.update, daemon=True).start()

	def update(self):
		self.bloqueo = True
		try:
			os.rename(os.path.join(settings.dir_data, 'languages_srv.json'), os.path.join(settings.dir_data, 'languages_srv.bak'))
			self.frame.connect_audio = wx.adv.Sound(os.path.join(settings.dir_root, "sound", "update.wav"))
			self.frame.connect_audio.Play(wx.adv.SOUND_ASYNC|wx.adv.SOUND_LOOP)
			self.frame.HelsinkiNLPModelFilter = HelsinkiNLPModelFilter(settings.file_json_filter)
			if self.frame.HelsinkiNLPModelFilter.filter_models():
				self.frame.HelsinkiNLPModelData.load_data()
				os.remove(os.path.join(settings.dir_data, 'languages_srv.bak'))
				self.frame.connect_audio.Stop()
				gui.messageBox(_("Se actualizo correctamente el catalogo de idiomas disponibles."), _("Información"), wx.OK| wx.ICON_INFORMATION)
				self.notebook.ChangeSelection(0)
				robot = wx.UIActionSimulator()
				robot.KeyUp(wx.WXK_RETURN)
				self.inicio()
			else:
				os.remove(os.path.join(settings.dir_data, 'languages_srv.json'))
				os.rename(os.path.join(settings.dir_data, 'languages_srv.bak'), os.path.join(settings.dir_data, 'languages_srv.json'))
				self.frame.connect_audio.Stop()
				msg = \
_("""No se a podido actualizar el catalogo de idiomas.

Vuelva a intentarlo en unos minutos.""")
				gui.messageBox(msg, _("Error"), wx.OK| wx.ICON_ERROR)
		except Exception as e:
			try:
				os.remove(os.path.join(settings.dir_data, 'languages_srv.json'))
			except:
				pass
			try:
				os.rename(os.path.join(settings.dir_data, 'languages_srv.bak'), os.path.join(settings.dir_data, 'languages_srv.json'))
			except:
				pass
			self.frame.connect_audio.Stop()
			msg = \
_("""Se a producido un error inesperado.

Error:

{}""").format(e)
			gui.messageBox(msg, _("Error"), wx.OK| wx.ICON_ERROR)
		self.bloqueo = False
		

	def OnKeyEvent(self, event):
		foco = wx.Window.FindFocus().GetId()
		robot = wx.UIActionSimulator()
		if (event.AltDown(), event.GetKeyCode()) == (True, 49): # Alt + 1 lleva a la pestaña url
			self.notebook.ChangeSelection(0)
			robot.KeyUp(wx.WXK_RETURN)
			self.available_listbox.SetFocus()
		elif (event.AltDown(), event.GetKeyCode()) == (True, 50): # Alt + 2 lleva a la pestaña búsqueda
			self.notebook.ChangeSelection(1)
			robot.KeyUp(wx.WXK_RETURN)
			self.installed_listbox.SetFocus()
		elif (event.ControlDown(), event.GetUnicodeKey()) == (True, 73): # Control+I anuncia información posición listbox.
			if foco in [100, 200]: # choice personalizado opciones y listbox resultados búsqueda y listbox favoritos
				obj = event.GetEventObject()
				if obj.GetString(obj.GetSelection()) in [_("Sin idiomas instalados")]: return
				msg = \
_("""Se encuentra en el resultado {} de {}""").format(obj.GetSelection()+1, obj.GetCount())
				ui.message(msg)

		elif (event.ControlDown(), event.GetUnicodeKey()) == (True, 70): # Control+F mueve foco en el listbox a número dado. o saca menú en campos de busqueda para filtrar
			if foco in [100, 200]: # listbox
				obj = event.GetEventObject()
				if obj.GetString(obj.GetSelection()) in [_("Sin idiomas instalados")]: return
				total = obj.GetCount()
				dlg = posicion(self, total)
				result = dlg.ShowModal()
				if result == 0: # movemos foco
					dlg.Destroy()
					obj.SetSelection(int(dlg.numero.GetValue()) - 1)
				else: # Cancelamos
					dlg.Destroy()
		elif event.GetUnicodeKey() == 27:
			self.on_close(None)
		else:
			event.Skip()
		
	def on_close(self, event):
		if not self.bloqueo:
			settings.IS_WinON = False
			self.Destroy()
			gui.mainFrame.postPopup()
		else:
			msg = \
_("""No se puede cerrar el dialogo.

Tiene una acción en curso.""")
			ui.message(msg)

##### Dialogo que muestra la descarga de los paquetes de idioma
class DescargaDialogo(wx.Dialog):
	"""
	Esta clase representa un diálogo que muestra el progreso de la descarga de modelos de idiomas.
	"""

	def __init__(self, directorio_destino, paquetes_idiomas, lista_idiomas):
		"""
		Inicializa el diálogo con los elementos gráficos necesarios y crea una instancia de DescargaHilo.

		:param directorio_destino: El directorio donde se guardarán los modelos descargados.
		:param paquetes_idiomas: Una lista de paquetes de idiomas a descargar.
		:param lista_idiomas: Una lista de idiomas.
		"""
		wx.Dialog.__init__(self, None, title="Descarga de Idiomas", size=(400, 200))
		
		self.directorio_destino = directorio_destino
		self.paquetes_idiomas = paquetes_idiomas
		self.lista_idiomas = lista_idiomas
		self.errores = []
		self.lang_errores = []
		
		# Crear los elementos gráficos
		self.init_ui()
		self.on_eventos()
		
		# Crear una instancia de DescargaHilo
		self.hilo_descarga = DescargaHilo(self.directorio_destino, self.paquetes_idiomas, self.lista_idiomas, self.actualizar_progreso, self.actualizar_estado)
		self.iniciar_descarga()
	

	def init_ui(self):
		"""
		Inicializa los elementos gráficos del diálogo.
		"""
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		
		self.texto_estado = wx.TextCtrl(self.panel, wx.ID_ANY, "", style=wx.TE_MULTILINE | wx.TE_READONLY)

		self.sizer.Add(self.texto_estado, 0, wx.ALL | wx.EXPAND, 5)
		
		self.barra_progreso = wx.Gauge(self.panel, range=100)
		self.sizer.Add(self.barra_progreso, 0, wx.ALL | wx.EXPAND, 5)
		
		self.panel.SetSizer(self.sizer)
	
	def on_eventos(self):
		self.texto_estado.Bind(wx.EVT_CONTEXT_MENU, self.on_pass)
		self.Bind(wx.EVT_CLOSE, self.on_pass)

	def iniciar_descarga(self):
		"""
		Inicia la descarga de modelos de idiomas.
		"""
		self.hilo_descarga.start()
	

	def actualizar_progreso(self, idioma_actual, total_idiomas, porcentaje):
		"""
		Actualiza la barra de progreso y el campo de texto con el progreso de la descarga.

		:param idioma_actual: El número del idioma que se está descargando actualmente.
		:param total_idiomas: El total de idiomas a descargar.
		:param porcentaje: El porcentaje de la descarga actual.
		"""
		self.barra_progreso.SetValue(porcentaje)
	

	def actualizar_estado(self, estado, evento=None):
		"""
		Actualiza el estado de la descarga (éxito, cancelado, error).

		:param estado: El estado actual de la descarga.
		:param evento: Información recibida.
		"""
		if estado == 'éxito':
			num = len(self.errores)
			if not num:
				msg = \
_("""Descarga completada con éxito

El servidor de traducción se reiniciará cuando acepte.""")
				wx.MessageBox(msg, _('Información'), wx.OK | wx.ICON_INFORMATION)
				if self.IsModal():
					self.EndModal(0)
				else:
					self.Close()
			else:
				if num == len(self.lista_idiomas): # Mismos fallos que idiomas.
					msg = \
_("""No se han podido instalar los idiomas seleccionados.

Inténtelo de nuevo.""")
					wx.MessageBox(msg, _('Error'), wx.OK | wx.ICON_ERROR)
					if self.IsModal():
						self.EndModal(2)
					else:
						self.Close()
				else:
					msg = \
_("""Se han instalado parte de los idiomas seleccionados.

Pero hay idiomas que no se han podido instalar.

Le dejo el idioma y el error perteneciente.

{}

El servidor de traducción se reiniciará cuando acepte.""").format("\n".join([f"Idioma:\n\n{idioma}\n\nError:\n\n{error}\n" for idioma, error in zip(self.lang_errores, self.errores)]))
					wx.MessageBox(msg, _('Información'), wx.OK | wx.ICON_INFORMATION)
					if self.IsModal():
						self.EndModal(1)
					else:
						self.Close()
		elif estado == 'error':
			self.errores.append(evento[0])
			self.lang_errores.append(evento[1])
		elif estado == 'eliminar':
			try:
				shutil.rmtree(evento)
			except Exception as e:
				pass
		elif estado == "Información":
			self.texto_estado.Clear()
			self.texto_estado.AppendText(f"Descargando idioma {self.lista_idiomas[evento[0] - 1]}...\n[{evento[0]} de {evento[1]}]")
	

	def on_pass(self, event):
		return

##### Clase para el hilo de descarga de paquetes de idioma
class DescargaHilo(Thread):
	"""
	Esta clase representa un hilo que se encarga de descargar los modelos de idiomas.
	"""
	def __init__(self, directorio_destino, paquetes_idiomas, lista_idiomas, callback_progreso, callback_estado):
		"""
		Inicializa el hilo de descarga.

		:param directorio_destino: El directorio donde se guardarán los modelos descargados.
		:param paquetes_idiomas: Una lista de paquetes de idiomas a descargar.
		:param lista_idiomas: Una lista de idiomas.
		:param callback_progreso: Una función callback para actualizar el progreso de la descarga.
		:param callback_estado: Una función callback para actualizar el estado de la descarga (éxito, cancelado, error).
		"""
		Thread.__init__(self)
		self.daemon = True
		self.directorio_destino = directorio_destino
		self.paquetes_idiomas = paquetes_idiomas
		self.lista_idiomas = lista_idiomas
		self.callback_progreso = callback_progreso
		self.callback_estado = callback_estado
		self.descarga_actual = None
		self.descargando = False
		self.modelo_actual_path = None
	
	def run(self):
		"""
		Este es el método principal que gestiona la descarga de los modelos.
		"""
		self.descargando = True
		for i, modelo in enumerate(self.paquetes_idiomas):
			self.descarga_actual = modelo
			self.modelo_actual_path = os.path.join(self.directorio_destino, modelo.split('/')[-1])
			self.download_model(self.lista_idiomas[i], i+1, len(self.lista_idiomas))
		
		self.callback_estado('éxito')

	def download_model(self, model_name, idioma_actual, total_idiomas):
		"""
		Esta función descarga un modelo específico y guarda los archivos esenciales en el directorio de modelos.
		"""
		def progress_callback(count, block_size, total_size):
			percentage = int(count * block_size * 100 / total_size)
			self.callback_progreso(idioma_actual, total_idiomas, percentage)
		
		self.callback_estado("Información", [idioma_actual, total_idiomas])

		model_path = os.path.join(self.directorio_destino, self.descarga_actual.split('/')[-1])
		if not os.path.exists(model_path):
			os.makedirs(model_path)

		essential_files = [
			"pytorch_model.bin", 
			"config.json", 
			"tokenizer_config.json", 
			"vocab.json", 
			"source.spm",
			"target.spm"
		]
		base_url = f"https://huggingface.co/{self.descarga_actual}/resolve/main/"
		
		for file in essential_files:
			file_url = base_url + file
			try:
				request.urlretrieve(file_url, os.path.join(model_path, file), progress_callback)
			except (error.HTTPError, error.URLError, FileNotFoundError, Exception) as e:
				self.callback_estado("error", [e, self.lista_idiomas[idioma_actual - 1]])
				self.limpiar_descarga()
				return

	def limpiar_descarga(self):
		"""
		Elimina cualquier rastro de una descarga cancelada.
		"""
		self.callback_estado("eliminar", self.modelo_actual_path)
##### Dialogo de ajustes
class SettingsDialog(wx.Dialog):
	def __init__(self, parent, frame):
		super(SettingsDialog, self).__init__(parent, -1)

		settings.IS_WinON = True
		self.SetSize((800, 600))
		self.SetTitle(_("Configuración de Traductor Offline"))

		self.frame = frame

		idiomas_origen, idiomas_destino = zip(*self.frame.HelsinkiNLPModelData.get_languages_installed())
		self.idiomas_origen = tuple(sorted(set(idiomas_origen), key=idiomas_origen.index))
		self.idiomas_destino = tuple(sorted(set(idiomas_destino), key=idiomas_destino.index))
		self.panelPrincipal = wx.Panel(self, wx.ID_ANY)

		sizerPrincipal = wx.BoxSizer(wx.VERTICAL)

		self.lista = wx.Listbook(self.panelPrincipal, wx.ID_ANY)
		sizerPrincipal.Add(self.lista, 1, wx.EXPAND, 0)

####
		self.panelGeneral = wx.Panel(self.lista, wx.ID_ANY)
		self.lista.AddPage(self.panelGeneral, _("General"))

		sizerGeneral = wx.BoxSizer(wx.VERTICAL)

		label_1 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("Seleccione un idioma de &origen:"))
		sizerGeneral.Add(label_1, 0, wx.EXPAND, 0)

		self.choiceOrigen = wx.Choice(self.panelGeneral, 201)
		sizerGeneral.Add(self.choiceOrigen, 0, wx.EXPAND, 0)

		label_3 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("Seleccione un idioma de &destino:"))
		sizerGeneral.Add(label_3, 0, wx.EXPAND, 0)

		self.choiceDestino = wx.Choice(self.panelGeneral, 202)
		sizerGeneral.Add(self.choiceDestino, 0, wx.EXPAND, 0)

		self.checkboxAutoDetectar = wx.CheckBox(self.panelGeneral, wx.ID_ANY, _("Activar o desactivar auto detectar idioma de origen (opción experimental)"))
		sizerGeneral.Add(self.checkboxAutoDetectar, 0, wx.EXPAND, 0)

		self.checkboxCache = wx.CheckBox(self.panelGeneral, wx.ID_ANY, _("Activar o desactivar la cache de traducción"))
		sizerGeneral.Add(self.checkboxCache, 0, wx.EXPAND, 0)
####
		sizerEstadoBotones = wx.BoxSizer(wx.HORIZONTAL)
		sizerPrincipal.Add(sizerEstadoBotones, 0, wx.EXPAND, 0)

		self.aceptarBTN = wx.Button(self.panelPrincipal, 101, _("&Aceptar"))
		sizerEstadoBotones.Add(self.aceptarBTN, 2, wx.CENTRE, 0)

		self.cancelarBTN = wx.Button(self.panelPrincipal, 102, _("&Cancelar"))
		sizerEstadoBotones.Add(self.cancelarBTN, 2, wx.CENTRE, 0)

		self.panelGeneral.SetSizer(sizerGeneral)

		self.panelPrincipal.SetSizer(sizerPrincipal)

		self.Layout()
		self.CenterOnScreen()
		self.eventos()

	def eventos(self):
		self.Bind(wx.EVT_BUTTON,self.onBoton)
		self.Bind(wx.EVT_CHAR_HOOK, self.onkeyVentanaDialogo)
		self.Bind(wx.EVT_CLOSE, self.onSalir)
		self.inicio()

	def inicio(self):
		self.choiceOrigen.Clear()
		self.choiceDestino.Clear()
		self.choiceOrigen.Append([_("Seleccione un idioma")] + [self.frame.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][i] for i in self.idiomas_origen])
		self.choiceDestino.Append([_("Seleccione un idioma")] + [self.frame.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][i] for i in self.idiomas_destino])
		self.choiceOrigen.SetSelection(0 if settings.choiceLangOrigen == "0" else self.idiomas_origen.index(settings.choiceLangOrigen) + 1)
		self.choiceDestino.SetSelection(0 if settings.choiceLangDestino == "0" else self.idiomas_destino.index(settings.choiceLangDestino) + 1)
		self.checkboxAutoDetectar.SetValue(settings.chkAutoDetect)
		self.checkboxCache.SetValue(settings.chkCache)
		self.choiceOrigen.SetFocus()

	def onBoton(self, event):
		id = event.GetId()
		if id == 101: # Aceptar
			if self.choiceOrigen.GetSelection() ==0 or  self.choiceDestino.GetSelection() == 0:
				gui.messageBox(_("Es obligatorio seleccionar un idioma origen y destino."), _("Error"), wx.OK| wx.ICON_ERROR)
				self.choiceOrigen.SetFocus()
				return

			if self.choiceOrigen.GetString(self.choiceOrigen.GetSelection()) == self.choiceDestino.GetString(self.choiceDestino.GetSelection()):
				gui.messageBox(_("No puede elegir el mismo idioma en origen y destino."), _("Error"), wx.OK| wx.ICON_ERROR)
				self.choiceOrigen.SetFocus()
				return

			settings.choiceLangOrigen = self.idiomas_origen[self.choiceOrigen.GetSelection() - 1]
			settings.choiceLangDestino = self.idiomas_destino[self.choiceDestino.GetSelection() - 1]
			settings.chkAutoDetect = self.checkboxAutoDetectar.GetValue()
			settings.chkCache = self.checkboxCache.GetValue()
			settings.guardaConfiguracion()
			self.onSalir(None)

		elif id == 102: # Cerrar
			self.onSalir(None)

	def onkeyVentanaDialogo(self, event):
		if event.GetKeyCode() == 27: # Pulsamos ESC y cerramos la ventana
			self.onSalir(None)
		else:
			event.Skip()

	def onSalir(self, event):
		settings.IS_WinON = False
		self.Destroy()
		gui.mainFrame.postPopup()


#####  Parte interface Historial
class HistoryDialog(wx.Dialog):
	def __init__(self, parent, frame):
		super(HistoryDialog, self).__init__(parent, -1)

		settings.IS_WinON = True
		self.SetSize((800, 600))
		self.SetTitle(_("Historial de Traductor Offline"))
		self.IS_Active = False

		self.frame = frame
		self.historialOrigen = utilidades.limpiaLista(list(settings.historialOrigen))
		self.historialDestino = utilidades.limpiaLista(list(settings.historialDestino))

		self.panelGeneral = wx.Panel(self, wx.ID_ANY)

		sizerGeneral = wx.BoxSizer(wx.VERTICAL)

#		label_1 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("&Buscar:"))
#		sizerGeneral.Add(label_1, 0, wx.EXPAND, 0)

#		self.textoBuscar = wx.TextCtrl(self.panelGeneral, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)
#		sizerGeneral.Add(self.textoBuscar, 0, wx.EXPAND, 0)

		label_2 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("&Lista texto original:"))
		sizerGeneral.Add(label_2, 0, wx.EXPAND, 0)

		self.listboxOriginal = wx.ListBox(self.panelGeneral, wx.ID_ANY)
		sizerGeneral.Add(self.listboxOriginal, 1, wx.EXPAND, 0)

		label_3 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("Texto &original:"))
		sizerGeneral.Add(label_3, 0, wx.EXPAND, 0)

		self.textoOrigen = wx.TextCtrl(self.panelGeneral, wx.ID_ANY, "", style=wx.TE_MULTILINE | wx.TE_READONLY)
		sizerGeneral.Add(self.textoOrigen, 0, wx.EXPAND, 0)

		label_4 = wx.StaticText(self.panelGeneral, wx.ID_ANY, _("Texto &traducido:"))
		sizerGeneral.Add(label_4, 0, wx.EXPAND, 0)

		self.textoTraducido = wx.TextCtrl(self.panelGeneral, wx.ID_ANY, "", style=wx.TE_MULTILINE | wx.TE_READONLY)
		sizerGeneral.Add(self.textoTraducido, 0, wx.EXPAND, 0)

		sizerBotones = wx.BoxSizer(wx.HORIZONTAL)
		sizerGeneral.Add(sizerBotones, 0, wx.EXPAND, 0)

		self.button_1 = wx.Button(self.panelGeneral, 101, _("&Copiar al portapapeles"))
		sizerBotones.Add(self.button_1, 2, wx.CENTRE, 0)

		self.button_3 = wx.Button(self.panelGeneral, 102, _("Borrar &historial"))
		sizerBotones.Add(self.button_3, 2, wx.CENTRE, 0)

		self.button_4 = wx.Button(self.panelGeneral, 103, _("&Refrescar historial"))
		sizerBotones.Add(self.button_4, 2, wx.CENTRE, 0)

		self.button_5 = wx.Button(self.panelGeneral, 104, _("Cerrar"))
		sizerBotones.Add(self.button_5, 2, wx.CENTRE, 0)

		self.panelGeneral.SetSizer(sizerGeneral)

		self.Layout()
		self.CenterOnScreen()
		self.eventos()
		self.inicio()

	def eventos(self):
		self.Bind(wx.EVT_BUTTON,self.onBoton)
		self.listboxOriginal.Bind(wx.EVT_KEY_UP, self.onLisbox)
		self.Bind(wx.EVT_CHAR_HOOK, self.onkeyVentanaDialogo)
		self.Bind(wx.EVT_CLOSE, self.onSalir)

	def inicio(self):
		self.listboxOriginal.Append(self.historialOrigen)
		self.listboxOriginal.SetSelection(0)
		self.listboxOriginal.SetFocus()
		self.onEstado()

	def onEstado(self):
		indice = self.listboxOriginal.GetSelection()
		self.textoOrigen.Clear()
		self.textoTraducido.Clear()
		self.textoOrigen.AppendText(self.historialOrigen[indice])
		self.textoTraducido.AppendText(self.historialDestino[indice])
		self.textoOrigen.SetInsertionPoint(0) 
		self.textoTraducido.SetInsertionPoint(0) 

	def onLisbox(self, event):
		if self.listboxOriginal.GetSelection() == -1:
			pass
		else:
			self.onEstado()

	def onBoton(self, event):
		id = event.GetId()
		if id == 101: # Copiar
			menu = wx.Menu()
			menu.Append(1, _("Copiar texto &original"))
			menu.Append(2, _("Copiar texto &traducido"))
			menu.Append(3, _("&Copiar origen y traducido"))
			menu.Bind(wx.EVT_MENU, self.onCopiaPortapapeles)
			self.button_1.PopupMenu(menu)

		elif id == 102: # Borrar
			settings.historialOrigen.clear()
			settings.historialDestino.clear()
			self.onSalir(None)
		elif id == 103: # Refrescar
			del self.historialOrigen[:]
			del self.historialDestino[:]
			self.historialOrigen = utilidades.limpiaLista(list(settings.historialOrigen))
			self.historialDestino = utilidades.limpiaLista(list(settings.historialDestino))
			self.listboxOriginal.Clear()
			self.listboxOriginal.Append(self.historialOrigen)
			self.listboxOriginal.SetSelection(0)
			self.listboxOriginal.SetFocus()
			self.onEstado()

		elif id == 104: # Cerrar
			self.onSalir(None)

	def onCopiaPortapapeles(self, event):
		id = event.GetId()
		if id == 1: # origen
			msg = \
_("""Copiado texto origen""")
			Clipboard().put(self.textoOrigen.GetValue())
		elif id == 2: # traducido
			msg = \
_("""Copiado texto traducido""")
			Clipboard().put(self.textoTraducido.GetValue())
		elif id == 3: # origen y traducido
			msg = \
_("""Copiado texto origen y traducido""")
			Clipboard().put("{}\n{}".format(self.textoOrigen.GetValue(), self.textoTraducido.GetValue()))
		notify = wx.adv.NotificationMessage(title=_("Información"), message=msg, parent=None, flags=wx.ICON_INFORMATION)
		notify.Show(timeout=10)

	def onkeyVentanaDialogo(self, event):
		if (event.ControlDown(), event.GetKeyCode()) == (True, 73):
			msg = \
_("""Se encuentra en la posición {} de {}""").format(self.listboxOriginal.GetSelection()+1, self.listboxOriginal.GetCount())
			ui.message(msg)
		elif (event.ControlDown(), event.GetKeyCode()) == (True, 70):
			obj = event.GetEventObject()
			total = obj.GetCount()
			dlg = posicion(self, total)
			result = dlg.ShowModal()
			if result == 0: # movemos foco
				dlg.Destroy()
				obj.SetSelection(int(dlg.numero.GetValue()) - 1)
			else: # Cancelamos
				dlg.Destroy()

		elif event.GetKeyCode() == 27: # Pulsamos ESC y cerramos la ventana
			self.onSalir(None)
		else:
			event.Skip()

	def onSalir(self, event):
		if self.IS_Active:
			return
		else:
			settings.IS_WinON = False
			self.Destroy()
			gui.mainFrame.postPopup()

##### Clase de posición en los listbox
class posicion(wx.Dialog):
	def __init__(self, frame, datos):

		super(posicion, self).__init__(None, -1, title=_("Ir a la posición..."))

		self.frame = frame
		self.datos = datos

		self.Panel = wx.Panel(self)

		label1 = wx.StaticText(self.Panel, wx.ID_ANY, label=_("&Introduzca un número entre 1 y {}:").format(self.datos))
		self.numero = wx.TextCtrl(self.Panel, 101, "", style=wx.TE_PROCESS_ENTER)

		self.AceptarBTN = wx.Button(self.Panel, 0, label=_("&Aceptar"))
		self.Bind(wx.EVT_BUTTON, self.onAceptar, id=self.AceptarBTN.GetId())

		self.CancelarBTN = wx.Button(self.Panel, 1, label=_("Cancelar"))
		self.Bind(wx.EVT_BUTTON, self.onCancelar, id=self.CancelarBTN.GetId())

		self.Bind(wx.EVT_CHAR_HOOK, self.onkeyVentanaDialogo)

		sizeV = wx.BoxSizer(wx.VERTICAL)
		sizeH = wx.BoxSizer(wx.HORIZONTAL)

		sizeV.Add(label1, 0, wx.EXPAND)
		sizeV.Add(self.numero, 0, wx.EXPAND)

		sizeH.Add(self.AceptarBTN, 2, wx.EXPAND)
		sizeH.Add(self.CancelarBTN, 2, wx.EXPAND)

		sizeV.Add(sizeH, 0, wx.EXPAND)

		self.Panel.SetSizer(sizeV)

		self.Centre()

	def onAceptar(self, event):
		msg = \
_("""El campo solo admite números y no puede quedar vacío.

Solo se admite un número comprendido entre 1 y {}.""").format(self.datos)
		if not self.numero.GetValue():
			gui.messageBox(msg, _("Información"), wx.OK| wx.ICON_INFORMATION)
			self.numero.Clear()
			self.numero.SetFocus()
			return
		else:
			try:
				z = 1 <= int(self.numero.GetValue()) <= self.datos
			except ValueError:
				gui.messageBox(msg, _("Información"), wx.OK| wx.ICON_INFORMATION)
				self.numero.Clear()
				self.numero.SetFocus()
				return

			if z:
				if self.IsModal():
					self.EndModal(0)
				else:
					self.Close()
			else:
				gui.messageBox(msg, _("Información"), wx.OK| wx.ICON_INFORMATION)
				self.numero.Clear()
				self.numero.SetFocus()
				return

	def onkeyVentanaDialogo(self, event):
		foco = wx.Window.FindFocus().GetId()
		robot = wx.UIActionSimulator()
		if event.GetUnicodeKey() == wx.WXK_RETURN:
			if foco in [101]: # campo texto pasamos.
				self.onAceptar(None)

		elif event.GetKeyCode() == 27: # Pulsamos ESC y cerramos la ventana
			if self.IsModal():
				self.EndModal(1)
			else:
				self.Close()
		else:
			event.Skip()

	def onCancelar(self, event):
		if self.IsModal():
			self.EndModal(1)
		else:
			self.Close()


#####
class TraductorPortapapeles:
	def __init__(self, intervalo=1.0):
		self._intervalo = intervalo
		self._stop_event = Event()
		self._monitor_thread = Thread(target=self._monitor_portapapeles, daemon=True)

	def iniciar(self):
		if not self._monitor_thread.is_alive():
			self._monitor_thread.start()

	def detener(self):
		self._stop_event.set()

	def _get_text_from_clipboard(self):
		CF_TEXT = 1
		kernel32 = ctypes.windll.kernel32
		user32 = ctypes.windll.user32
		user32.OpenClipboard(0)
		try:
			if user32.IsClipboardFormatAvailable(CF_TEXT):
				data = user32.GetClipboardData(CF_TEXT)
				data_locked = kernel32.GlobalLock(data)
				text = ctypes.c_char_p(data_locked)
				value = text.value.decode('utf-8')
				kernel32.GlobalUnlock(data_locked)
				return value
		finally:
			user32.CloseClipboard()

	def _translate_text(self, text):
		# Aquí puedes incluir cualquier lógica de traducción que desees,
		# por ejemplo, llamando a una API de traducción.
		# Por ahora, solo devolveremos el texto original para demostrar que funciona.
		return text

	def _monitor_portapapeles(self):
		last_text = ""
		while not self._stop_event.is_set():
			try:
				current_text = self._get_text_from_clipboard()
				if current_text and current_text != last_text:
					translated_text = self._translate_text(current_text)
					print(f'Texto copiado: {current_text}')
					print(f'Texto traducido: {translated_text}')
					last_text = current_text
			except Exception as e:
				print(f'Error: {e}')
			time.sleep(self._intervalo)