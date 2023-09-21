# -*- coding: utf-8 -*-
# Copyright (C) 2023 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

# Carga NVDA
import globalVars
import speech
import languageHandler
from speech import *
import speechViewer
from eventHandler import FocusLossCancellableSpeechCommand
from queueHandler import eventQueue, queueFunction
# Carga estándar
import re
import string
# Carga personal
from .lib import mtranslate
from . import settings

def validar_string(input_string):
	url_pattern = re.compile(r'(?:http|https|ftp)://[^\s/$.?#].[^\s]*')
	email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

	try:
		if url_pattern.fullmatch(input_string) or email_pattern.fullmatch(input_string):
			return True
		else:
			return False
	except:
		return True

def es_linea_con_simbolo(linea):
	if not isinstance(linea, str):
		return False
	simbolos_adicionales = '—‘’“”«»•°±≠≤≥∞\t ++--==!=<=>=+=-=*=/=&&||-><-**__  '
	simbolos = re.escape(string.punctuation + simbolos_adicionales)
	patron = fr'^\s*[{simbolos}]+\s*$'
	return bool(re.fullmatch(patron, linea))

def funTranslate(text):
	try:
		appName = "{}_{}".format(globalVars.focusObject.appModule.appName, settings.choiceLangDestino)
	except:
		appName = "__global__"
                
	if settings._enableTranslation is False and settings._enableTranslationOnline is False:
		return text

	if es_linea_con_simbolo(text):
		return text

	try:
		if not bool(text.strip()):
			return text
	except:
		pass

	if settings.chkCache:
		appTable = settings._translationCache.get(appName, None)
		if appTable is None:
			settings._translationCache[appName] = {}
		translated = settings._translationCache[appName].get(text, None)
		if translated is not None and translated != text:
			return translated
	try:
		if settings._enableTranslation:
			translated = settings.cliente.comando(["{}cmdTrans".format(settings.idMaquina), [text, settings.choiceLangOrigen, settings.choiceLangDestino, settings.chkAutoDetect, settings.chkTextLargo]])
		else:
			prepared = text.encode('utf8', ':/')
			translated = mtranslate.translate(prepared, languageHandler.getLanguage()[:2])
	except Exception as e:
		return text
	if translated is None or len(translated) == 0:
		translated = text
	else:
		if settings.chkCache:
			settings._translationCache[appName][text] = translated
	return translated

def speak(speechSequence: SpeechSequence, priority: Spri = None):
	valid_list = [re.sub('  $', '', re.sub('^ +| +$', '', re.sub(' +', ' ', item))) for item in speechSequence if isinstance(item, str)]
	if settings._enableTranslation is False and settings._enableTranslationOnline is False:
		return settings._nvdaSpeak(speechSequence=speechSequence, priority=priority)

	if not valid_list:
		return settings._nvdaSpeak(speechSequence=speechSequence, priority=priority)

	newSpeechSequenceOrigen = []
	newSpeechSequenceDestino = []

	v = funTranslate(" ".join(valid_list))
	newSpeechSequenceOrigen.append(" ".join(valid_list))
	newSpeechSequenceDestino.append(v if v is not None else " ".join(valid_list))
	settings._nvdaSpeak(speechSequence=newSpeechSequenceDestino, priority=priority)
	settings._lastTranslatedText = " ".join(x if isinstance(x, str) else "" for x in newSpeechSequenceDestino)
	textDestino = getSequenceText(settings._lastTranslatedText)
	if textDestino.strip():
		if isinstance(newSpeechSequenceOrigen[0], str):
			if isinstance(newSpeechSequenceDestino[0], str):
				if newSpeechSequenceOrigen[0].replace(" ", "") == newSpeechSequenceDestino[0].replace(" ", ""):
					pass
				else:
					queueFunction(eventQueue, append_to_historyOrigen, newSpeechSequenceOrigen)
					queueFunction(eventQueue, append_to_historyDestino, newSpeechSequenceDestino)

def getSequenceText(sequence):
	return speechViewer.SPEECH_ITEM_SEPARATOR.join([x for x in sequence if isinstance(x, str)])

def append_to_historyOrigen(seq):
	seq = [command for command in seq if not isinstance(command, FocusLossCancellableSpeechCommand)]
	settings.historialOrigen.appendleft(seq[0])

def append_to_historyDestino(seq):
	seq = [command for command in seq if not isinstance(command, FocusLossCancellableSpeechCommand)]
	settings.historialDestino.appendleft(seq[0])
