# -*- coding: utf-8 -*-
# Copyright (C) 2023 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.
#
# Idea y parte de código obtenido de TRANSLATE del autor Yannick PLASSIARD
# Github: https://github.com/yplassiard/nvda-translate
#
# Carga NVDA
import globalPluginHandler
import addonHandler
import logHandler
import languageHandler
import globalVars
import core
import gui
import ui
import shellapi
import textInfos
import api
import speech
from speech import *
from scriptHandler import script, getLastScriptRepeatCount
# Carga estándar
import os
import sys
import wx
import wx.adv
import json
import re
import codecs
import tempfile
from threading import Thread
# Carga personal
from .lib import psutil
from . import settings
from . import guis
from . import message

# Carga traducción
addonHandler.initTranslation()

def disableInSecureMode(decoratedCls):
	"""
    Esta función deshabilita la ejecución de un objeto o clase en modo seguro.
    
    Parámetros:
    decoratedCls (object): El objeto o clase que se desea deshabilitar en modo seguro.

    Retorna:
    object: Retorna globalPluginHandler.GlobalPlugin si la aplicación está en modo seguro, de lo contrario retorna el objeto o clase original (decoratedCls).
	"""
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return decoratedCls

@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)

		if os.environ.get("ProgramFiles(x86)"):
			if hasattr(globalVars, "TranslateOffline"):
				self.postStartupHandler()
			core.postNvdaStartup.register(self.postStartupHandler)
			globalVars.TranslateOffline = None
		else:
			msg = \
_("""Se a detectado que la arquitectura de este equipo es de 32 bits.

Translate Offline necesita ser ejecutado en un equipo de 64 bits.

Se cancelará la carga del complemento.""")
			logHandler.log.error(msg)
			return

		self.HelsinkiNLPModelFilter = None
		self.HelsinkiNLPModelData = None
		self.connect_audio = None
		self.is_cargado = False

	def postStartupHandler(self):
		Thread(target=self.__inicio, daemon = True).start()

	def __inicio(self):
		if guis.utilidades.is_connected():
			if not os.path.isfile(settings.file_json_filter):
				self.HelsinkiNLPModelFilter = guis.HelsinkiNLPModelFilter(settings.file_json_filter)
				if not self.HelsinkiNLPModelFilter.filter_models():
					logHandler.log.error(_("Inicio del complemento cancelado."))
					return

		self.HelsinkiNLPModelData = guis.HelsinkiNLPModelData(settings.file_json_filter, settings.file_json_languages)
		self.HelsinkiNLPModelData.load_data()

		settings.setup()

		settings.idMaquina = str.encode(guis.utilidades.id_maquina())
		settings.puerto = guis.utilidades.obtenPuerto()

		try:
			PROCNAME = "TranslateOfflineSRV.exe"
			for proc in psutil.process_iter():
				if proc.name() == PROCNAME:
					proc.kill()
		except Exception as e:
			pass

		shellapi.ShellExecute(None, "open", os.path.join(settings.dir_srv, "TranslateOfflineSRV.exe"), "{} {}".format("localhost", settings.puerto, settings.procesamiento), settings.dir_srv, 10)

		if settings.chkCache:
			self.loadLocalCache()

		self.menu = gui.mainFrame.sysTrayIcon.preferencesMenu
		self.WXMenu = wx.Menu()
		self.mainItem = self.menu.AppendSubMenu(self.WXMenu, _("&Traductor Offline"), "")
		self.settingsItem = self.WXMenu.Append(wx.ID_ANY, _("&Configuración de Traductor Offline"), "")
		self.langSettingsItem = self.WXMenu.Append(wx.ID_ANY, _("&Gestor de idiomas"), "")
		self.rebootServer = self.WXMenu.Append(wx.ID_ANY, _("&Reiniciar el servidor y cliente"), "")
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onSettings, self.settingsItem)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onSettingsLang, self.langSettingsItem)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onReboot, self.rebootServer)

		from . import nvdaExtra

		settings._nvdaSpeak = speech._manager.speak
		settings._nvdaGetPropertiesSpeech = speech.getPropertiesSpeech
		speech._manager.speak = nvdaExtra.speak
		speech.getPropertiesSpeech = settings._nvdaGetPropertiesSpeech
		settings._enableTranslation = False
		settings._enableTranslationOnline = False

		self.is_cargado = True
		Thread(target=self.startServer, daemon = True).start()

	def startServer(self):
		if settings.IS_Sonido:
			self.connect_audio = wx.adv.Sound(os.path.join(settings.dir_root, "sound", "connect.wav"))
			self.connect_audio.Play(wx.adv.SOUND_ASYNC|wx.adv.SOUND_LOOP)

			settings.idMaquina = str.encode(guis.utilidades.id_maquina())
			settings.puerto = guis.utilidades.obtenPuerto()
			settings._enableTranslation = False

			try:
				PROCNAME = "TranslateOfflineSRV.exe"
				for proc in psutil.process_iter():
					if proc.name() == PROCNAME:
						proc.kill()
			except:
				pass

			shellapi.ShellExecute(None, "open", os.path.join(settings.dir_srv, "TranslateOfflineSRV.exe"), "{} {}".format("localhost", settings.puerto, settings.procesamiento), settings.dir_srv, 10)

		from . import client

		while True:
			if guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"):
				settings.cliente = client.Cliente()
				if not settings.cliente.returnCode:
					settings.IS_Cliente = False
				else:
					settings.IS_Cliente = True
					break

		if settings.IS_Sonido:
			self.connect_audio.Stop()
			settings.IS_Sonido = False
			settings.IS_Reinicio = False
			settings.IS_WinON = False

	def terminate(self):
		try:
			PROCNAME = "TranslateOfflineSRV.exe"
			for proc in psutil.process_iter():
				if proc.name() == PROCNAME:
					proc.kill()
		except:
			pass
		try:
			self.menu.Remove(self.mainItem)
		except Exception:
			pass
		try:
			settings.cliente.terminarServer()
		except:
			pass
		speech._manager.speak = settings._nvdaSpeak
		speech.getPropertiesSpeech = settings._nvdaGetPropertiesSpeech
		if settings.chkCache:
			self.saveLocalCache()
		core.postNvdaStartup.unregister(self.postStartupHandler)
		super().terminate()

	def onSettings(self, event):
		self.script_onSettings(None, True)

	def onSettingsLang(self, event):
		self.script_onSettingsLang(None, True)

	@script(gesture=None, description= _("Abre la configuración del complemento"), category= "TranslateOffline")
	def script_onSettings(self, event, menu=False):
		if settings.IS_Reinicio: gui.messageBox(message._msg1, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg1)
		elif guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"):
			if settings.IS_Cliente:
				if settings.IS_WinON: gui.messageBox(_("Ya hay una instancia de Traductor Offline abierta."), _("Información"), wx.ICON_INFORMATION) if menu else ui.message(_("Ya hay una instancia de Traductor Offline abierta."))
				elif settings.is_active_translate: gui.messageBox(_("Tiene una traducción en curso. Espere a que termine."), _("Información"), wx.ICON_INFORMATION) if menu else ui.message(_("Tiene una traducción en curso. Espere a que termine."))
				elif not len(self.HelsinkiNLPModelData.get_languages_installed()): gui.messageBox(message._msg2, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg2)
				else: settings._enableTranslation = False; HiloLauncher(self, 1).start()
			else: gui.messageBox(message._msg3, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg3)
		else: gui.messageBox(message._msg4, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg4)

	@script(gesture=None, description= _("Abre el Gestor de idiomas"), category= "TranslateOffline")
	def script_onSettingsLang(self, event, menu=False):
		if settings.IS_Reinicio: gui.messageBox(message._msg1, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg1)
		elif guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"):
			if settings.IS_Cliente:
				if settings.IS_WinON: gui.messageBox(_("Ya hay una instancia de Traductor Offline abierta."), _("Información"), wx.ICON_INFORMATION) if menu else ui.message(_("Ya hay una instancia de Traductor Offline abierta."))
				elif settings.is_active_translate: gui.messageBox(_("Tiene una traducción en curso. Espere a que termine."), _("Información"), wx.ICON_INFORMATION) if menu else ui.message(_("Tiene una traducción en curso. Espere a que termine.")); return
				else: settings._enableTranslation = False; HiloLauncher(self, 2).start()
			else: gui.messageBox(message._msg3, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg3)
		else: gui.messageBox(message._msg4, _("Información"), wx.ICON_INFORMATION) if menu else ui.message(message._msg4)

	def onReboot(self, event):
		try:
			settings.cliente.terminarServer()
		except:
			pass
		settings.IS_Sonido = True
		Thread(target=self.startServer, daemon = True).start()

	def textSpy(self, obj, opcion=0):
		# Inicio código obtenido de Buscador de definiciones de la RAE (DLEChecker) de Antonio Cascales
		if hasattr(obj.treeInterceptor, 'TextInfo') and not obj.treeInterceptor.passThrough:
			try: info = obj.treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
			except (RuntimeError, NotImplementedError): info = None
			if not info or info.isCollapsed: return False
			selectedText = info.text
			if opcion == 1: return selectedText
		else:
			try: 
				selectedText = obj.selection.text
				if opcion == 1: return selectedText
			except (RuntimeError, NotImplementedError): return False
			if obj.selection.text == "": return False
		return True if selectedText and opcion == 0 else selectedText if selectedText else False
		# Fin código obtenido de Buscador de definiciones de la RAE (DLEChecker) de Antonio Cascales

	def transSelect(self):
		obj = api.getFocusObject()
		if not obj or obj.windowClassName == 'ConsoleWindowClass': return
		temp = self.textSpy(obj, 1)
		if temp in [False, None]: ui.message(_("Sin selección para traducir")); return
		settings._enableTranslation = False
		settings.is_active_translate = True
		fichero_temp = os.path.join(tempfile.gettempdir(),"translate_offline_temp.txt")
		lineas_filtradas = [linea for linea in temp.splitlines() if re.sub('  $', '', re.sub('^ +| +$', '', re.sub(' +', ' ', linea)))]
		cadena_filtrada = '\n'.join(lineas_filtradas)
		with open(fichero_temp, "w", encoding="utf-8") as file: file.write(cadena_filtrada)
		with open(fichero_temp, 'r', encoding="UTF-8") as file: tmp_lines = file.read()
		self.connect_audio = wx.adv.Sound(os.path.join(settings.dir_root, "sound", "progress.wav"))
		self.connect_audio.Play(wx.adv.SOUND_ASYNC|wx.adv.SOUND_LOOP)
		if not bool(tmp_lines.strip()): settings.is_active_translate = False; self.connect_audio.Stop(); ui.message(_("Sin texto para traducir.")); return
		try: texto = settings.cliente.comando(["{}cmdTrans".format(settings.idMaquina), [tmp_lines, settings.choiceLangOrigen, settings.choiceLangDestino, settings.chkAutoDetect, True]])
		except: settings.is_active_translate = False; self.connect_audio.Stop(); ui.message(_("No se a podido obtener la traducción de lo seleccionado.")); return
		try: settings.is_active_translate = False; self.connect_audio.Stop(); ui.browseableMessage(texto, "Traducción", False)
		except: pass

	def loadLocalCache(self):
		path = settings.dir_cache
		if not os.path.exists(path):
			try: os.mkdir(path)
			except Exception as e: logHandler.log.error(f"Failed to create storage path: {path} ({e})"); return
		for entry in os.listdir(path):
			m = re.match("(.*)\.json$", entry)
			if m:
				appName = m.group(1)
				try: cacheFile = codecs.open(os.path.join(path, entry), "r", "utf-8")
				except: continue
				try: values = json.load(cacheFile); settings._translationCache[appName] = values
				except Exception as e: logHandler.log.error(f"Cannot read or decode data from {path}: {e}"); continue
				finally: cacheFile.close()

	def saveLocalCache(self):
		path = settings.dir_cache
		for appName in settings._translationCache:
			file = os.path.join(path, f"{appName}.json")
			try:
				with codecs.open(file, "w", "utf-8") as cacheFile: json.dump(settings._translationCache[appName], cacheFile, ensure_ascii=False)
			except Exception as e: logHandler.log.error(f"Failed to save translation cache for {appName} to {file}: {e}"); continue

	@script(gesture=None, description= _("Activa o desactiva la traducción simultanea Offline"), category= "TranslateOffline")
	def script_toggleTranslateOffline(self, event):
		if settings._enableTranslationOnline: ui.message(_("No se puede activar la traducción Offline si la traducción Online está en marcha.")); return
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("La traducción no puede ser activada mientras haya una ventana de Traductor Offline abierta")); return
		if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0": ui.message(message._msg5); return
		if settings.is_active_translate: ui.message(_("Tiene una traducción en curso. Espere a que termine.")); return
		settings._enableTranslation = not settings._enableTranslation
		ui.message(_("Traducción activada.") if settings._enableTranslation else _("Traducción desactivada."))
		if settings.chkCache: (self.loadLocalCache if settings._enableTranslation else self.saveLocalCache)()

	@script(gesture=None, description= _("Activa o desactiva la traducción simultanea Online"), category= "TranslateOffline")
	def script_toggleTranslateOnline(self, event):
		if not self.is_cargado: ui.message(_("El complemento se esta cargando. Espere unos segundos.")); return
		if settings.is_active_translate or settings._enableTranslation: ui.message(_("No se puede activar la traducción Online si alguna de las funciones Offline están en marcha.")); return
		settings._enableTranslationOnline = not settings._enableTranslationOnline
		ui.message(_("Traducción activada.")) if settings._enableTranslationOnline else ui.message(_("Traducción desactivada."))
		if settings.chkCache: self.loadLocalCache() if settings._enableTranslationOnline else self.saveLocalCache()


	@script(gesture=None, description= _("Activa o desactiva la autodetección de idioma"), category= "TranslateOffline")
	def script_toggleAutoLang(self, event):
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("La autodetección no puede ser activada o desactivada mientras haya una ventana de Traductor Offline abierta")); return
		temp = settings._enableTranslation
		if settings._enableTranslation: settings._enableTranslation = False; temp = True; self.saveLocalCache() if settings.chkCache else None
		else: temp = False
		settings.chkAutoDetect = not settings.chkAutoDetect
		ui.message(_("Autodetección de idioma activada.")) if settings.chkAutoDetect else ui.message(_("Autodetección de idioma desactivada."))
		settings.setConfig("autodetect", settings.chkAutoDetect)
		if temp: settings._enableTranslation = True; self.loadLocalCache() if settings.chkCache else None

	@script(gesture=None, description= _("Activa o desactiva la cache de traducción"), category= "TranslateOffline")
	def script_toggleCache(self, event):
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("La activación o desactivación de la cache no puede hacerse mientras haya una ventana de Traductor Offline abierta")); return
		temp = settings._enableTranslation
		if settings._enableTranslation: settings._enableTranslation = False; temp = True; self.saveLocalCache() if settings.chkCache else None
		else: temp = False
		settings.chkCache = not settings.chkCache
		ui.message(_("Cache de traducción activada.")) if settings.chkCache else ui.message(_("Cache de traducción desactivada."))
		settings.setConfig("cache", settings.chkCache)
		if temp: settings._enableTranslation = True; self.loadLocalCache() if settings.chkCache else None

	@script(gesture=None, description= _("Cambiar rápidamente el idioma origen"), category= "TranslateOffline")
	def script_changeLangOrigen(self, event):
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("El idioma origen no puede cambiarse rápidamente si hay una ventana de Traductor Offline abierta.")); return
		if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0": ui.message(message._msg5); return
		temp = settings._enableTranslation
		if settings._enableTranslation: settings._enableTranslation = False; temp = True; self.saveLocalCache() if settings.chkCache else None
		else: temp = False
		origenes, destinos = zip(*self.HelsinkiNLPModelData.get_languages_installed())
		seen = set()
		temp_origen = tuple(x for x in origenes if x != settings.choiceLangDestino and not (x in seen or seen.add(x)))
		temp_indice = temp_origen.index(settings.choiceLangOrigen)
		settings.indiceLangOrigen = 0 if temp_indice >= len(temp_origen) - 1 else temp_indice + 1
		settings.choiceLangOrigen = temp_origen[settings.indiceLangOrigen]
		ui.message(_("Idioma origen cambiado a {}").format(self.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][temp_origen[settings.indiceLangOrigen]]))
		settings.setConfig("langOrigen",settings.choiceLangOrigen)
		if temp: settings._enableTranslation = True; self.loadLocalCache() if settings.chkCache else None

	@script(gesture=None, description= _("Cambiar rápidamente el idioma destino"), category= "TranslateOffline")
	def script_changeLangDestino(self, event):
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("El idioma destino no puede cambiarse rápidamente si hay una ventana de Traductor Offline abierta.")); return
		if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangDestino == "0" or settings.choiceLangOrigen == "0": ui.message(message._msg5); return
		temp = settings._enableTranslation
		if settings._enableTranslation: settings._enableTranslation = False; temp = True; self.saveLocalCache() if settings.chkCache else None
		else: temp = False
		origenes, destinos = zip(*self.HelsinkiNLPModelData.get_languages_installed())
		seen = set()
		temp_destino = tuple(x for x in destinos if x != settings.choiceLangOrigen and not (x in seen or seen.add(x)))
		temp_indice = temp_destino.index(settings.choiceLangDestino)
		settings.indiceLangDestino = 0 if temp_indice >= len(temp_destino) - 1 else temp_indice + 1
		settings.choiceLangDestino = temp_destino[settings.indiceLangDestino]
		ui.message(_("Idioma destino cambiado a {}").format(self.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][temp_destino[settings.indiceLangDestino]]))
		settings.setConfig("langDestino",settings.choiceLangDestino)
		if temp: settings._enableTranslation = True; self.loadLocalCache() if settings.chkCache else None

	@script(gesture=None, description= _("Intercambia lenguaje origen y destino"), category= "TranslateOffline")
	def script_changeLangOrder(self, event):
		if settings.IS_Reinicio: ui.message(message._msg1); return
		if not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"): ui.message(message._msg4); return
		if not settings.IS_Cliente: ui.message(message._msg3); return
		if settings.IS_WinON: ui.message(_("Los idiomas no pueden intercambiarse si hay una ventana de Traductor Offline abierta.")); return
		if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0": ui.message(message._msg5); return
		temp = settings._enableTranslation
		if settings._enableTranslation: 
			settings._enableTranslation = False
			temp = True
			if settings.chkCache: self.saveLocalCache()
		else: 
			temp = False
		idiomas = self.HelsinkiNLPModelData.get_languages_installed()
		if [settings.choiceLangDestino, settings.choiceLangOrigen] in idiomas:
			settings.choiceLangOrigen, settings.choiceLangDestino = settings.choiceLangDestino, settings.choiceLangOrigen
			settings.setConfig("langOrigen", settings.choiceLangOrigen)
			settings.setConfig("langDestino", settings.choiceLangDestino)
			cambio = self.HelsinkiNLPModelData.get_language_names("es" if languageHandler.getLanguage()[:2] == "es" else "en", [settings.choiceLangOrigen, settings.choiceLangDestino])
			ui.message(_("Idiomas intercambiados correctamente: {} - {}").format(cambio[0], cambio[1]))
		else:
			ui.message(_("No se pueden intercambiar los idiomas.\n\nEl intercambio de idiomas solo puede hacerse si un paquete de idioma origen e idioma destino está instalado."))
		if temp:
			settings._enableTranslation = True
			if settings.chkCache: self.loadLocalCache()

	@script(gesture=None, description= _("Eliminar todas las traducciones en caché para todas las aplicaciones"), category= "TranslateOffline")
	def script_flushAllCache(self, event):
		if getLastScriptRepeatCount() == 0:
			ui.message(_("Pulse dos veces para eliminar todas las traducciones en caché de todas las aplicaciones."))
			return
		settings._translationCache = {}
		path = settings.dir_cache
		error = False
		if os.path.isdir(path):
			if not os.listdir(path):
				ui.message(_("No hay ninguna cache para borrar."))
				return
			for entry in os.listdir(path):
				try:
					os.unlink(os.path.join(path, entry))
				except Exception:
					logHandler.log.error(_("Fallo al eliminar {entry}").format(entry=entry))
					error = True
		else:
			ui.message(_("El directorio de la cache no existe."))
			return
		ui.message(_("Se ha eliminado toda la cache.")) if not error else ui.message(_("No se a podido eliminar toda la cache."))

	@script(gesture=None, description= _("Eliminar la caché de traducción para la aplicación enfocada actualmente"), category= "TranslateOffline")
	def script_flushCurrentAppCache(self, event):
		try:
			appName = globalVars.focusObject.appModule.appName
		except:
			ui.message(_("No hay aplicación enfocada."))
			return
		if getLastScriptRepeatCount() == 0:
			ui.message(_("Pulse dos veces para eliminar todas las traducciones de {} en lenguaje {}").format(appName, settings.choiceLangDestino))
			return
		settings._translationCache[appName] = {}
		fullPath = os.path.join(settings.dir_cache, "{}_{}.json".format(appName, settings.choiceLangDestino))
		if os.path.exists(fullPath):
			try:
				os.unlink(fullPath)
				ui.message(_("Se ha borrado la cache de la aplicación {} correctamente.").format(appName))
			except Exception as e:
				logHandler.log.error(_("Fallo al borrar la cache de la aplicación {} : {}").format(appName, e))
				ui.message(_("Error al borrar la caché de traducción de la aplicación."))
		else:
			ui.message(_("No hay traducciones guardadas para {}").format(appName))

	@script(gesture=None, description= _("Copiar el ultimo texto traducido al portapapeles"), category= "TranslateOffline")
	def script_copyLastTranslation(self, event):
		if settings.is_active_translate: ui.message(_("Tiene una traducción en curso. Espere a que termine.")); return
		if settings._lastTranslatedText and len(settings._lastTranslatedText) > 0: guis.Clipboard().put(settings._lastTranslatedText); ui.message(_("Se a copiado lo siguiente al portapapeles: {}").format(settings._lastTranslatedText))
		else: ui.message(_("No se a podido copiar nada al portapapeles"))

	@script(gesture=None, description= _("Traducir texto seleccionado"), category= "TranslateOffline")
	def script_transSelect(self, event):
		if settings.IS_Reinicio:
			ui.message(message._msg1)
		elif not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"):
			ui.message(message._msg4)
		elif not settings.IS_Cliente:
			ui.message(message._msg3)
		elif settings.IS_WinON:
			ui.message(_("La traducción no puede ser activada mientras haya una ventana de Traductor Offline abierta"))
		elif not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0":
			ui.message(message._msg5)
		elif settings.is_active_translate:
			ui.message(_("Tiene una traducción en curso. Espere a que termine."))
		else:
			Thread(target=self.transSelect, daemon=True).start()

	@script(gesture=None, description= _("Mostrar historial de Traductor Offline"), category= "TranslateOffline")
	def script_historial(self, event):
		if settings.IS_Reinicio:
			ui.message(message._msg1)
		elif len(guis.utilidades.limpiaLista(list(settings.historialOrigen))) == 0:
			ui.message(_("No hay nada en el historial de Traductor Offline"))
		elif not guis.utilidades.procesoCHK("TranslateOfflineSRV.exe"):
			ui.message(message._msg4)
		elif not settings.IS_Cliente:
			ui.message(message._msg3)
		elif settings.IS_WinON:
			ui.message(_("Ya hay una instancia de Traductor Offline abierta."))
		else:
			settings._enableTranslation = False
			HiloLauncher(self, 3).start()

	@script(gesture=None, description= _("Obtener información de Traductor Offline"), category= "TranslateOffline")
	def script_info(self, event):
		msg = \
_("""Idioma origen actual: {}.
Idioma destino actual: {}.
Paquetes de idioma instalados: {}.
Detección de idioma: {}.
Cache de traducción: {}.
Memoria usada por el servidor: {}.
Procesamiento de carga: {}.""").format(
	_("Sin idiomas instalados o seleccionados") if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0" else self.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][settings.choiceLangOrigen],
	_("Sin idiomas instalados o seleccionados") if not len(self.HelsinkiNLPModelData.get_languages_installed()) or settings.choiceLangOrigen == "0" or settings.choiceLangDestino == "0" else self.HelsinkiNLPModelData.data_lang["es" if languageHandler.getLanguage()[:2] == "es" else "en"][settings.choiceLangDestino],
	len(self.HelsinkiNLPModelData.get_languages_installed()),
	_("Activada") if settings.chkAutoDetect else _("Desactivada"),
	_("Activada") if settings.chkCache else _("Desactivada"),
	next((f"{round(proc.info['memory_info'].rss / (1024 ** 3), 2)} GB" for proc in psutil.process_iter(['pid', 'name', 'memory_info']) if proc.info['name'] == 'TranslateOfflineSRV.exe'), _("Sin información")),
	settings.procesamiento.upper(),
)
		ui.message(msg)

class HiloLauncher(Thread):
	def __init__(self, frame, opcion):
		super(HiloLauncher, self).__init__()

		self.frame = frame
		self.opcion = opcion
		self.daemon = True

	def run(self):
		def appLauncherAjustes():
			self._main = guis.SettingsDialog(gui.mainFrame, self.frame)
			gui.mainFrame.prePopup()
			self._main.Show()

		def appLauncherGestor():
			self._main = guis.LanguageDialog(gui.mainFrame, self.frame)
			gui.mainFrame.prePopup()
			self._main.Show()

		def appLauncherHistory():
			self._main = guis.HistoryDialog(gui.mainFrame, self)
			gui.mainFrame.prePopup()
			self._main.Show()

		if self.opcion == 1:
			wx.CallAfter(appLauncherAjustes)
		elif self.opcion == 2:
			wx.CallAfter(appLauncherGestor)
		elif self.opcion == 3:
			wx.CallAfter(appLauncherHistory)

