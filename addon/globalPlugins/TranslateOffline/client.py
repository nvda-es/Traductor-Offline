# -*- coding: utf-8 -*-
# Copyright (C) 2022 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

import os
import sys
dirAddon=os.path.dirname(__file__)
sys.path.append(dirAddon)
sys.path.append(os.path.join(dirAddon, "lib"))
import hmac
import pathlib
#hmac.__path__.append(os.path.join(dirAddon, "lib"))
from multiprocessing.connection import Client
del sys.path[-2:]
from . import settings

class Cliente():
	def __init__(self):

		try:
			self.conexion = Client(("localhost", int(settings.puerto)), authkey=settings.idMaquina)
			self.returnCode = True
			settings.IS_Cliente = True
		except Exception as e:
			self.returnCode = False
			settings.cliente = None
			settings.IS_Cliente = False

	def comando(self, valor):
		try:
			self.conexion.send(valor)
		# Recibimos el mensaje inicial que nos dice cuántas partes esperar
			control_message = self.conexion.recv()
			num_parts = control_message["parts"]
    
			# Inicializamos una lista para almacenar cada parte recibida
			result_parts = []
    
			# Recibimos cada parte y la añadimos a la lista
			for _ in range(num_parts):
				data_message = self.conexion.recv()
				result_parts.append(data_message["content"])
    
			# Reconstruimos y devolvemos el mensaje completo
			complete_result = "".join(result_parts)
			return complete_result
		except Exception as e:
			settings.cliente = None
			settings.IS_Cliente = False


	def terminar(self):
		try:
			self.conexion.send(["{}closeClient".format(settings.idMaquina), ""])
			self.conexion.close()
			settings.cliente = None
			settings.IS_Cliente = False
		except:
			settings.cliente = None
			settings.IS_Cliente = False

	def terminarServer(self):
		try:
			self.conexion.send(["{}closeServer".format(settings.idMaquina), ""])
			self.conexion.close()
			settings.cliente = None
			settings.IS_Cliente = False
		except:
			settings.cliente = None
			settings.IS_Cliente = False
