@echo off
REM Construye y verifica el ejecutable en Windows. Ejecutar desde la raiz del proyecto
REM con el entorno virtual activado:   scripts\empaquetar_windows.bat
pip install pyinstaller || exit /b 1
python scripts\empaquetar.py || exit /b 1
echo.
echo Ejecutable listo: dist\AlquilerEquipos\AlquilerEquipos.exe
echo Copie la carpeta completa dist\AlquilerEquipos a cualquier PC con Windows 10/11.
echo Para activar la IA: copie alquiler.env.ejemplo como alquiler.env (misma carpeta),
echo pegue su clave de Groq y ejecute:  AlquilerEquipos.exe --probar-ia
