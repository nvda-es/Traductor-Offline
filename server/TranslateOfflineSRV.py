#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from multiprocessing import Queue
from multiprocessing.connection import Listener
from transformers import MarianMTModel, MarianTokenizer
import torch
import fasttext
import wx
import sys
import os
import uuid
import re
import time
import gestor_logs

dir_logs =os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logs")
dir_models =os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "models")
if not os.path.isdir(dir_logs): # Si no existe creamos directorio
	os.makedirs(dir_logs)
if not os.path.isdir(dir_models): # Si no existe creamos directorio
	os.makedirs(dir_models)

# Cargamos logs
log = gestor_logs.GestorLogs(False, False, os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logs", "error_global.txt"))

class HelsinkiTranslator:
	def __init__(self, device="cpu"):

		self.models_directory = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "models")
		self.available_models = []
		self.loaded_models = {}
		if not os.path.exists(self.models_directory):
			os.makedirs(self.models_directory)
		self.device = torch.device(device)  # Acepta un parámetro para elegir entre CPU y GPU
		self.idMaquina = str.encode(self.id_maquina())
		fasttext.FastText.eprint = lambda x: None # Evita mensaje de cambio de API.
		self.model_auto = fasttext.load_model(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "auto", "lid.176.bin")) # "lid.176.ftz"

	def id_maquina(self):
		return str(uuid.uuid1(uuid.getnode(),0))[24:]

	def list_models(self, source_language, target_language):
		model_name_prefix = "Helsinki-NLP/opus-mt-"
		self.available_models = [
			f"{model_name_prefix}{source_language}-{target_language}",
			f"{model_name_prefix}{target_language}-{source_language}"
		]
		return self.available_models

	def load_models(self):
		for model_name in os.listdir(self.models_directory):
			model_path = os.path.join(self.models_directory, model_name)
			if os.path.isdir(model_path):
				language_codes = model_name.split('-')[-2:]
				model_key = f"Helsinki-NLP/opus-mt-{language_codes[0]}-{language_codes[1]}"
				self.loaded_models[model_key] = {
					"model": MarianMTModel.from_pretrained(model_path).to(self.device),
					"tokenizer": MarianTokenizer.from_pretrained(model_path)
				}
#		print("Models loaded successfully")

	def list_loaded_models(self):
		return list(self.loaded_models.keys())

	def translate(self, text, source_language, target_language, auto=False, largo=False):
		if auto:
			try:
				temp_source_language = self.model_auto.predict(text, k=1, threshold=0.1)[0][0][9:]
			except:
				temp_source_language = source_language
		else:
			temp_source_language = source_language

		if temp_source_language == target_language:
			return text

		model_name = f"Helsinki-NLP/opus-mt-{temp_source_language}-{target_language}"
		if model_name not in self.loaded_models:
			# Intento de traducción indirecta a través del inglés
			if temp_source_language != 'en' and target_language != 'en':
				text = "-" + text
				try:
					# Traducción al inglés
					intermediate_model_name = f"Helsinki-NLP/opus-mt-{temp_source_language}-en"
					intermediate_model = self.loaded_models[intermediate_model_name]["model"]
					intermediate_tokenizer = self.loaded_models[intermediate_model_name]["tokenizer"]
					text = intermediate_model.generate(**intermediate_tokenizer(text, return_tensors="pt", padding=True), max_length=512)[0]
					text = intermediate_tokenizer.decode(text, skip_special_tokens=True)

					# Traducción del inglés al idioma destino
					final_model_name = f"Helsinki-NLP/opus-mt-en-{target_language}"
					final_model = self.loaded_models[final_model_name]["model"]
					final_tokenizer = self.loaded_models[final_model_name]["tokenizer"]
					text = final_model.generate(**final_tokenizer(text, return_tensors="pt", padding=True), max_length=512)[0]
					text = final_tokenizer.decode(text, skip_special_tokens=True)
					
					return text[1:]
				except:
					# En caso de error, devuelve el texto original
					return text
			else:
				# Si no es posible realizar una traducción indirecta, devuelve el texto original
				return text

		model = self.loaded_models[model_name]["model"]
		tokenizer = self.loaded_models[model_name]["tokenizer"]

		if largo:
			max_length = 512

			# Paso 1: Dividir el texto en párrafos
			paragraphs = text.split('\n')

			translated_paragraphs = []
			for paragraph in paragraphs:
				# Paso 2: Verificar la longitud en tokens del párrafo
				tokenized_paragraph = tokenizer(paragraph, return_length=True, padding=True, truncation=True)
				paragraph_length_in_tokens = tokenized_paragraph['length']

				# Si el párrafo es más largo que max_length, lo dividimos en segmentos más pequeños
				if paragraph_length_in_tokens > max_length:
					words = paragraph.split()
					segments = []
					segment = ""
					for word in words:
						if len(tokenizer(segment + word, return_length=True, padding=True, truncation=True)['input_ids'][0]) <= max_length:
							segment = segment + " " + word
						else:
							segments.append(segment.strip())
							segment = word
					segments.append(segment.strip())

					# Paso 3: Traducir cada segmento individualmente y unirlos para formar el párrafo traducido
					translated_segment_texts = []
					for segment in segments:
						tokenized_segment = tokenizer(segment, return_tensors="pt", padding=True, truncation=True)
						translated_segment = model.generate(**tokenized_segment)
						translated_segment_texts.append(tokenizer.decode(translated_segment[0], skip_special_tokens=True))
					translated_paragraphs.append(" ".join(translated_segment_texts))
				else:
					# Si el párrafo es más corto que max_length, lo traducimos directamente
					tokenized_paragraph = tokenizer(paragraph, return_tensors="pt", padding=True, truncation=True)
					translated_paragraph = model.generate(**tokenized_paragraph)
					translated_paragraphs.append(tokenizer.decode(translated_paragraph[0], skip_special_tokens=True))

			# Paso 4: Combinar los párrafos traducidos con saltos de línea
			translated_text = "\n\n".join(translated_paragraphs)
		else:
			text = "-" + text

			texto_tokenizado = tokenizer.prepare_seq2seq_batch([text], return_tensors='pt')
			traduccion = model.generate(**texto_tokenizado)
			translated_text = tokenizer.decode(traduccion[0], skip_special_tokens=True)[1:]

		return translated_text

class servidor():
	def __init__(self, direccion, puerto, procesamiento="cpu"):

		self.direccion = direccion
		self.puerto = puerto
		self.procesamiento = procesamiento
		self.datos = HelsinkiTranslator("cpu" if self.procesamiento == "cpu" else "gpu")
		self.datos.load_models()
		self.password = self.datos.idMaquina

		try:
			self.listener = Listener((self.direccion, self.puerto),authkey=self.password, )
			self.conexion = None
			self.escucha = None
			self.runServer = True
			self.returnCode = True
		except OSError as e:
			self.returnCode = False

	def run(self):
		while self.runServer:
			self.conexion = self.listener.accept()
			while True:
				max_reconnect_attempts = 5
				reconnect_wait_time = 2  # tiempo de espera en segundos

				for attempt in range(max_reconnect_attempts):
					try:
						self.escucha = self.conexion.recv()
						# Si la recepción es exitosa, salir del bucle
						break
					except EOFError:
						# Cerrando la conexión actual (si aún está abierta) antes de intentar reconectar
						if self.conexion:
							self.conexion.close()
						# Intentando reconectar
						self.conexion = self.listener.accept()
						time.sleep(reconnect_wait_time)  # Esperando antes de intentar de nuevo
					except Exception as e:
						# Cerrando el programa debido a un error inesperado
						sys.exit(1)
				
				self.parametro = self.escucha[0]
				self.valor = self.escucha[1]
				if self.parametro == "{}cmdTrans".format(self.password):
					self.translate(self.valor)
				elif self.parametro == "{}closeClient".format(self.password):
					self.closeClient()
					break
				elif self.parametro == "{}closeServer".format(self.password):
					self.closeServer()
					break

	def translate(self, orden):
		resultado = self.datos.translate(orden[0], orden[1], orden[2], orden[3], orden[4])
		MAX_SIZE = 1024  # Establecemos un tamaño máximo para cada mensaje (esto puede ajustarse)
    
		# Dividimos el resultado en múltiples partes si es necesario
		result_parts = [resultado[i:i+MAX_SIZE] for i in range(0, len(resultado), MAX_SIZE)]
    
		# Enviamos un mensaje inicial con el número de partes que el cliente debe esperar
		self.conexion.send({"type": "control", "parts": len(result_parts)})
    
		# Enviamos cada parte individualmente
		for part in result_parts:
			self.conexion.send({"type": "data", "content": part})

	def closeClient(self):
		self.conexion.close()

	def closeServer(self):
		self.conexion.close()
		self.runServer = False
		self.listener.close()

class Aplicacion(wx.App):
	def mensaje(self, mensaje, titulo, valor):
		if valor == 0:
			self.parametro = wx.OK | wx.ICON_INFORMATION
		elif valor == 1:
			self.parametro = wx.OK | wx.ICON_ERROR
		dlg = wx.MessageDialog(None, mensaje, titulo, self.parametro)
		dlg.SetOKLabel("&Accept")
		dlg.ShowModal()
		dlg.Destroy()

	def OnInit(self):

		self.name = "TranslateOfflineSRV%s".format(wx.GetUserId())
		self.instance = wx.SingleInstanceChecker(self.name)
		if self.instance.IsAnotherRunning():
			msg = \
"""TranslateOfflineSRV is already running.

Close the other instance before running again."""
			self.mensaje(msg, "Error", 1)
			return False
		if len(sys.argv) == 3:
			p = servidor(sys.argv[1], int(sys.argv[2]))
			if p.returnCode:
				p.run()
				return True
		if len(sys.argv) == 4:
			p = servidor(sys.argv[1], int(sys.argv[2]), sys.argv[3])
			if p.returnCode:
				p.run()
				return True
			else:
				msg = \
"""TranslateOfflineSRV failed to start.

Some of the given parameters are already being used by another application."""
				self.mensaje(msg, "Error", 1)
				return False
		else:
			msg = \
"""TranslateOfflineSRV needs threee parameters to be executed.

localhost, listening port and processing (CPU/GPU)."""
			self.mensaje(msg, "Error", 1)
			return False

if __name__ == '__main__':
	try:
		app = Aplicacion(redirect=False)
	except:
		sys.exit(1)
	app.MainLoop()

