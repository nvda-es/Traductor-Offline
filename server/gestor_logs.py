#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import sys
import logging

class GestorLogs:
	"""
La clase "GestorLogs" se encarga de gestionar los registros de logs en diferentes canales de información, errores y errores globales.
Argumentos de entrada:
•canal_info_archivo: Ruta del archivo donde se almacenarán los registros de información.
•canal_error_archivo: Ruta del archivo donde se almacenarán los registros de errores.
•canal_global_archivo: Ruta del archivo donde se almacenarán los registros de errores globales.
Ejemplo de uso:
python
# Importar la clase
from GestorLogs import GestorLogs

# Crear una instancia de la clase
gestor_logs = GestorLogs('canal_info.log', 'canal_error.log', 'canal_global.log')

# Registrar un mensaje de información
gestor_logs.log_info('Este es un mensaje de información.')

# Registrar un mensaje de error
gestor_logs.log_error('Este es un mensaje de error.')

# Registrar un mensaje de error global
gestor_logs.log_error_global('Este es un mensaje de error global.')

# Lanzar una excepción para probar la interceptación de errores globales
raise Exception('Se ha producido un error global.')
El método "init" inicializa los diferentes canales de logs para almacenar los registros en los archivos correspondientes. Cada canal tiene un nivel de registro distinto: "INFO" para el canal de información, "ERROR" para el canal de errores y "ERROR" también para el canal de errores globales.
El método "log_info" registra un mensaje de información en el canal correspondiente.
El método "log_error" registra un mensaje de error en el canal correspondiente.
El método "log_error_global" registra un mensaje de error global en el canal correspondiente.
El método "interceptar_errores_globales" se encarga de interceptar los errores globales y registrarlos en el canal correspondiente.
En resumen, la clase "GestorLogs" es una herramienta útil para gestionar los registros de logs en diferentes canales y archivos, lo que permite mantener un registro detallado de los eventos y errores en una aplicación.
	"""
	def __init__(self, canal_info_archivo, canal_error_archivo, canal_global_archivo):

		# Canal de información
		self.logger_info = logging.getLogger('canal_info')
		self.logger_info.setLevel(logging.INFO)
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		if canal_info_archivo:
			handler = logging.FileHandler(canal_info_archivo)
			handler.setFormatter(formatter)
			self.logger_info.addHandler(handler)

		# Canal de errores
		self.logger_error = logging.getLogger('canal_error')
		self.logger_error.setLevel(logging.ERROR)
		if canal_error_archivo:
			handler = logging.FileHandler(canal_error_archivo)
			handler.setFormatter(formatter)
			self.logger_error.addHandler(handler)

		# Canal de errores globales
		self.logger_global = logging.getLogger('canal_global')
		self.logger_global.setLevel(logging.ERROR)
		handler = logging.FileHandler(canal_global_archivo)
		handler.setFormatter(formatter)
		self.logger_global.addHandler(handler)

		# Habilitar la interceptación de errores globales
		sys.excepthook = self.interceptar_errores_globales

	def info(self, mensaje):
		self.logger_info.info(mensaje)

	def log_error(self, mensaje):
		self.logger_error.error(mensaje)

	def log_error_global(self, mensaje):
		self.logger_global.error(mensaje)

	def interceptar_errores_globales(self, exctype, value, traceback):
		mensaje = f'Error global: {value}'
		self.logger_global.error(mensaje, exc_info=(exctype, value, traceback))
