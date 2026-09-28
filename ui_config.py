"""Presentation constants shared by the web page and the native Tk app."""
from firmware.timer_logic import THRESHOLDS

PRESETS = (30, 25, 20, 15, 10, 5, 1)
COLORS = dict(off='#eaf0f3', green='#4ce7a0', yellow='#f9dd69', orange='#ffad60',
              red='#ff6e79', overdue='#ff6e79')
LABELS = dict(off='BEREIT', green='REDEZEIT', yellow='LETZTE 5 MINUTEN', orange='LETZTE MINUTE',
              red='ZEIT ABGELAUFEN', overdue='ÜBERZOGEN')

_limit = dict(THRESHOLDS)
# Derived from the thresholds so the legend cannot drift from the actual phases.
LEGEND = ('Grün · über %d min' % (_limit['yellow'] // 60000),
          'Gelb · bis %d min' % (_limit['yellow'] // 60000),
          'Orange · bis %d min' % (_limit['orange'] // 60000),
          'Rot · Zeit abgelaufen',
          'Blinkend · %d s überzogen' % (-_limit['overdue'] // 1000))
