"""Presentation constants shared by the web page and the native Tk app."""
from firmware.timer_logic import THRESHOLDS

PRESETS = (30, 25, 20, 15, 10, 5, 1)
COLORS = dict(off='#eaf0f3', green='#4ce7a0', yellow='#f9dd69', orange='#ffad60',
              red='#ff6e79', overdue='#ff6e79')
# Dark phase of the blinking overdue countdown; also the static legend swatch for it.
OVERDUE_DIM = '#71343c'
LEGEND_COLORS = dict(COLORS, overdue=OVERDUE_DIM)
LABELS = dict(off='BEREIT', green='REDEZEIT', yellow='LETZTE 5 MINUTEN', orange='LETZTE MINUTE',
              red='ZEIT ABGELAUFEN', overdue='ÜBERZOGEN')

_limit = dict(THRESHOLDS)
# Derived from the thresholds so the legend cannot drift from the actual phases.
# Each entry is (phase, text); the phase selects the colour swatch shown next to it.
LEGEND = (('green', 'Grün · über %d min' % (_limit['yellow'] // 60000)),
          ('yellow', 'Gelb · bis %d min' % (_limit['yellow'] // 60000)),
          ('orange', 'Orange · bis %d min' % (_limit['orange'] // 60000)),
          ('red', 'Rot · Zeit abgelaufen'),
          ('overdue', 'Blinkend · %d s überzogen' % (-_limit['overdue'] // 1000)))
