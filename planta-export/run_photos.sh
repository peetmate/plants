#!/bin/zsh
# Unattended runner for planta_photos.py: keeps the screen awake and re-runs the
# capture (which RESUMES from the manifest) until the whole list is done or a pass
# makes no progress. Lets the ~7h job finish without any agent babysitting it.
#   ./run_photos.sh            # logs to photo_run.log
cd "${0:A:h}"
TARGET=861                     # ~plants in the collection (manifest = plants + header)
adb shell svc power stayon true >/dev/null 2>&1

for i in $(seq 1 50); do
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
    echo "STOP: no progress this pass (phone locked/unplugged?)" >> photo_run.log; break
  fi
  sleep 5
done
adb shell svc power stayon false >/dev/null 2>&1
echo "runner exited" >> photo_run.log
