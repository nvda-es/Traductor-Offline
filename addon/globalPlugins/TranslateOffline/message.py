# -*- coding: utf-8 -*-
# Copyright (C) 2023 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

# Carga NVDA
import addonHandler

# Carga traducción
addonHandler.initTranslation()

_msg1 = \
_("""Traductor Offline no puede usarse en este momento.

Tiene una acción por terminar.

Puede reiniciar NVDA o reiniciar en Preferencias / Traductor Offline / Reiniciar el servidor y cliente.""")

_msg2 = \
_("""No tiene ningún idioma instalado.

Instale un idioma desde el Gestor de idiomas.""")

_msg3 = \
_("""Si acaba de iniciar NVDA espere unos segundos el cliente se esta cargando.

Si hace tiempo que inicio NVDA puede que la comunicación entre cliente y servidor se perdiera.

Reinicie NVDA o reinicie el cliente desde Preferencias / Traductor Offline / Reiniciar el servidor y cliente.""")

_msg4 = \
_("""El servidor de traducciones no esta activo.

Reinicie NVDA o reinicie el servidor desde Preferencias / Traductor Offline / Reiniciar el servidor y cliente.""")

_msg5 = \
_("""No tiene ningún idioma instalado o seleccionado.

Instale un idioma desde el Gestor de idiomas o seleccione un idioma desde la configuración de Traductor Offline.""")
