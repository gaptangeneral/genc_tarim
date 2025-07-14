@echo off
chcp 1254
REM Projenin tam yoluna git.
cd "C:\GencTarimSistem\genc_tarim"

REM Python'un tam yolunu kullanarak Waitress'i çalıştır.
REM AŞAĞIDAKİ PYTHON YOLUNUN DOĞRU OLDUĞUNDAN EMİN OLUN.
"C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe" -m waitress --host=0.0.0.0 --port=8000 genc_tarim.wsgi:application >> "C:\GencTarimSistem\genc_tarim\logs\server.log" 2>&1