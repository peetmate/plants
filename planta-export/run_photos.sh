#!/bin/zsh
# Unattended runner for planta_photos.py: keeps the screen awake and re-runs the
# capture (which RESUMES from the manifest) until the whole list is done or a pass
# makes no progress. Lets the ~7h job finish without any agent babysitting it.
#   ./run_photos.sh            # logs to photo_run.log
cd "${0:A:h}"
TARGET=861                     # ~plants in the collection (manifest = plants + header)
adb shell svc power stayon true >/dev/null 2>&1

noprog=0
for i in $(seq 1 80); do
  # wake the screen + bring Planta to front before each pass (survives the phone
  # locking or another app stealing focus between passes)
  adb shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
  adb shell am start -n com.stromming.planta/.main.views.MainActivity >/dev/null 2>&1
  sleep 2
  before=$(wc -l < planta_photos_manifest.csv 2>/dev/null | tr -d ' ')
  before=${before:-0}
  echo "=== pass $i start (manifest=$before) ===" >> photo_run.log
  python3 planta_photos.py >> photo_run.log 2>&1
  after=$(wc -l < planta_photos_manifest.csv 2>/dev/null | tr -d ' ')
  after=${after:-0}
  echo "=== pass $i end (manifest=$after) ===" >> photo_run.log
  if [ "$after" -ge "$TARGET" ]; then
    echo "DONE: reached $after manifest rows" >> photo_run.log; break
  fi
  if [ "$after" = "$before" ]; then
    noprog=$((noprog + 1))
    echo "no progress (streak $noprog)" >> photo_run.log
    [ "$noprog" -ge 4 ] && { echo "STOP: 4 passes with no progress" >> photo_run.log; break; }
    sleep 20            # transient (locked/popup); wait, then retry
  else
    noprog=0
    sleep 5
  fi
done
adb shell svc power stayon false >/dev/null 2>&1
echo "runner exited" >> photo_run.log
