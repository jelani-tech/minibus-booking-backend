"""Applications autorisées à recevoir un jeton (claim `aud`).

Un jeton émis pour une application est refusé sur les routes d'une autre : un
jeton client ne donne jamais accès aux routes chauffeur, et inversement.
"""

CUSTOMER_APP = 'customer-app'
DRIVER_APP = 'driver-app'
ADMIN_APP = 'admin-app'

ALL_AUDIENCES = (CUSTOMER_APP, DRIVER_APP, ADMIN_APP)
